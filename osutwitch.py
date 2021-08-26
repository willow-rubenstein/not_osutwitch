# pyinstaller.exe --onefile --console --icon=icon.ico osutwitch.py --name OsuTwitch_v4_win64

# osu!twitch is on public release v4
from twitchio.ext import commands
import json
import requests
import argparse
import os
import re
import sys
import time
from typing import Pattern
import random
import asyncio
import twitchio
import datetime
import time
import maskpass

ILLEGAL_CHARS = re.compile(r"[\<\>:\"\/\\\|\?*]")
OSU_URL = "https://osu.ppy.sh/home"
OSU_SESSION_URL = "https://osu.ppy.sh/session"
OSU_SEARCH_URL = "https://osu.ppy.sh/beatmapsets/search"

with open("osutwitch.log", "w+") as f:
    f.write("")

def log(message, moduleName=None):
    with open("osutwitch.log", "a") as f:
        if moduleName != None:
            f.write(f"{datetime.datetime.now()} - {moduleName}: {message}\n")
        else:
            f.write(f"{datetime.datetime.now()}: {message}\n")

class loginLoop:
    def __init__(self):
        self.session = requests.Session()
        self.main()    
    
    def login(self, data):
        log("attempting to log into osu! network as user", "loginLoop.login")
        data["_token"] = self.get_token()
        headers = {"referer": OSU_URL}
        res = self.session.post(OSU_SESSION_URL, data=data, headers=headers)
        if res.status_code != requests.codes.ok:
            log("Login failed.", "loginLoop.login")
            return 400
        else:
            log("Logged in successfully.", "loginLoop.login")
            return 200

    def get_token(self):
        homepage = self.session.get(OSU_URL)
        regex = re.compile(r".*?csrf-token.*?content=\"(.*?)\">", re.DOTALL)
        match = regex.match(homepage.text)
        try:
            csrf_token = match.group(1)
        except Exception as e:
            log(f"A fatal error has occured. Full traceback: {e}", "loginLoop.get_token")
        return csrf_token

    def main(self):
        clear = lambda: os.system('cls')
        x = True
        while x == True:
            username = maskpass.askpass("What is your osu! username (case-sensitive)? ", "*")
            clear()
            password = maskpass.askpass("What is your osu! password (case-sensitive)? ", "*")
            clear()
            if self.login({'username': username, 'password': password}) != 400:
                self.session.close()
                x = False
                log(f"Logged into osu! network successfully as user {username}", "loginLoop.loginTest")
                print("Logged in successfully to osu! please do not close this window (you can minimize it)")
                os.environ['OSU_USERNAME'] = username
                os.environ['OSU_PASSWORD'] = password
            else:
                print("Failed to log in. Will allow another attempt in 30 seconds (to avoid possible rate-limiting from osu! server)")
                time.sleep(30)
                self.session.close()
                self.session = requests.Session()

class Downloader:
    def __init__(self, songname, qtype, credentials, options):
        self.thisSet = {}
        self.songname = songname
        self.qtype = qtype
        self.session = requests.Session()
        self.credentials = credentials
        self.options = options
        self.login()

    def getToken(self):
        log("Getting token for osu! api", "Downloader.getToken")
        params = {
            'client_id': <id>,
            'client_secret': <secret>,
            'scope': 'public',
            "grant_type": "client_credentials"
        }
        r = requests.post('https://osu.ppy.sh/oauth/token', data=params)
        return r.json()['access_token']
    
    def optionsLogic(self, options, item):
        if options != None:
            log("options did not return none. Searching for specified BPM and star difficulties", "Downloader.optionsLogic")
            x = 0
            for item in item['beatmaps']:
                if item['bpm'] <= options['bpmMax'] and item['difficulty_rating'] <=options['starMax'] and item['difficulty_rating'] >= options['starMin']:
                    pass
                else:
                    x += 1   
            if x > 0:
                if options['allowHigherStarSets'] == True and x > 1 and item['bpm'] <= options['bpmMax']:
                    log("Att: user has set option \"allowHigherStarSets\" to true. Will download this set because there are multiple difficulties.", "Downloader.optionsLogic")
                    return True
                else:
                    log("Returning False because map does not map options", "Downloader.optionsLogic")
                    return False
            else:
                log("Returning True because map passes set options", "Downloader.optionsLogic")
                return True
        else:
            log("options.json not found! Returning True and will create new options file on next startup.")
            return True

    def lookup(self, name, type):
        token = self.getToken()
        headers = {"Authorization": str(f"Bearer {token}")}
        if type == 0: #0 = artist/title
            url = f"https://osu.ppy.sh/api/v2/beatmapsets/search/?q={name}?s=any"
            log(f"looking up beatmap type Artist", "Downloader.lookup")
            r = requests.get(url, headers=headers)
            r1 = r.json()
            notFound = True
            for item in r1['beatmapsets']:
                if item['artist'].lower() in name.lower() and notFound == True:
                    log('found beatmap with provided query. Fetching first result.', 'Downloader.lookup')
                    notFound = False
                    songid = item['id']
                    log(f'song id is {songid}', 'Downloader.lookup')
                    log('getting download link for song...', "Downloader.lookup")
                    url = f'https://osu.ppy.sh/beatmapsets/{songid}'
                    r = requests.get(url, allow_redirects=False)
                    filename = str(f"{songid} {item['artist']} - {item['title']}")
                    log("seeing if specified name already exists in user's osu! folder.", "Downloader.lookup")
                    log("Specified file does not exist.", "Downloader.lookup")
                    log('Testing specified song for options.json match', "Downloader.lookup")
                    if self.optionsLogic(self.options, item) == True:
                        log(f'returning data {url} and {filename}')
                        return {'url': url, 'filename': filename}
                    else:
                        log("Att: song did not pass options specified. Skipping this query.", "Downloader.lookup")
                        return None
        else:
            log(f"looking up beatmap type URL with url {name}", "Downloader.lookup")
            pattern = r'https://osu.ppy.sh/beatmapsets/'
            sid = re.sub(pattern, '', name)
            url = f"https://osu.ppy.sh/api/v2/beatmapsets/{sid}"
            r = requests.get(url, headers=headers)
            log(f"Item returned status {r}", "Downloader.lookup")
            item = json.loads(r.text)
            #log(f"returned json {item} from request", "Downloader.lookup")
            filename = str(f"{sid} {item['artist']} - {item['title']}")
            log(f"Succesfully generated filename {filename}", "Downloader.lookup")
            log("Specified file does not exist.", "Downloader.lookup")
            log('Testing specified song for options.json match', "Downloader.lookup")
            if self.optionsLogic(self.options, item) == True:
                log(f'returning data {name} and {filename}', "Downloader.lookup")
                return {'url': name, 'filename': filename}
            else:
                log("Att: song did not pass options specified. Skipping this query.", "Downloader.lookup")
                return None
            
    def login(self):
        log("Logging into osu! network as user", "Downloader.login")
        data = {'username': os.environ['OSU_USERNAME'], 'password': os.environ["OSU_PASSWORD"]}
        data["_token"] = self.get_token()
        headers = {"referer": OSU_URL}
        res = self.session.post(OSU_SESSION_URL, data=data, headers=headers)
        if res.status_code != requests.codes.ok:
            log("Login failed.", "Downloader.login")
        else:
            log("Logged in successfully.", "Downloader.login")

    def get_token(self):
        homepage = self.session.get(OSU_URL)
        regex = re.compile(r".*?csrf-token.*?content=\"(.*?)\">", re.DOTALL)
        match = regex.match(homepage.text)
        csrf_token = match.group(1)
        return csrf_token

    def download_beatmapset_file(self):
        if self.qtype == "url":
            log("alternate search type found...", "Downloader.download_beatmapset_file")
            self.thisSet = self.lookup(self.songname, type=1)
        else:
            log("Doing artist/title lookup", "Downloader.download_beatmapset_file")
            self.thisSet = self.lookup(self.songname, type=0)
        if self.thisSet != None:
            log('Starting beatmapset download...', "Downloader.download_beatmapset_file")
            headers = {"referer": self.thisSet['url']}
            response = self.session.get(self.thisSet['url']+ "/download", headers=headers)
            if response.status_code == requests.codes.ok:
                log(f"{response.status_code} - Download successful", "Downloader.download_beatmapset_file")
                self.write_beatmapset_file(str(self.thisSet['filename']), response.content)
                return 1
            else:
                log(f"{response.status_code} - Download failed", "Downloader.download_beatmapset_file")
                return 0
        else:
            log("Skipping download because song did not pass options/existance check.", "Downloader.download_beatmapset_file")
            return 2

    def write_beatmapset_file(self, filename, data):
        log(f"Writing file: {filename}.osz", "Downloader.write_beatmapset_file")
        with open(f"{filename}.osz", "wb") as outfile:
            outfile.write(data)
        log("File write successful... attempting to add the song to the user's library...", "Downloader.write_beatmapset_file")
        try:
            os.startfile(f"{filename}.osz")
            log("File write successful and added to user's library", "Downloader.write_beatmapset_file")
        except Exception as e:
            log(f"An exception has occured while trying to write the file. Full traceback: {e}", "Downloader.write_beatmapset_file")

    def run(self):
        x = self.download_beatmapset_file()
        y = {
            0: "Failed to download song.",
            1: "Downloaded song successfully.",
            2: "Skipped song download because it was either already in library or didn't fit streamer's preferences"
        }   
        return y[x]

async def osuDownload(songname, qtype, credentials, options):
    loader = Downloader(songname, qtype=qtype, credentials=credentials, options=options)
    statusReturn = loader.run()
    return statusReturn

with open('options.json', 'r') as f:
    options = json.load(f)

bot = commands.Bot(
    token="",
    client_id="",
    nick='osu_twitchbot',
    prefix='!',
    initial_channels=[options['channelName']]
)

@bot.command(name="osumap")
async def _osumap(ctx, *args):
    global options
    qtype = "artist"
    argPass = ''.join(args)
    await ctx.send(f'attempting to download osu! map @{ctx.author.name}')
    if argPass.find('http') != -1:
        log("https found in mapname. Sending query type 'url'", "global._osumap")
        mapname = argPass
        if argPass.find("#") != -1:
            mapname = argPass[:-int(len(argPass)-argPass.find("#"))]
        qtype = "url"
    else:
        log("https not found in mapname", "global._osumap")
        mapname = ' '.join(args)  
    try:
        
        await ctx.send(f"@{ctx.author.name} searching osu! api for song")
        statusReturn = await osuDownload(mapname, qtype, credentials={'username': os.environ["OSU_USERNAME"], 'password': os.environ["OSU_PASSWORD"]}, options=options)
        await ctx.send(f"@{ctx.author.name} {statusReturn}")
    except Exception as e:
        await ctx.send(f"@{ctx.author.name} failed to download osu! song because the streamer is stupid")
        roastUserOptions = [
            'you fucking broke my bot, cunt.',
            'woooooowwww. smooth moves buddy. you broke my bot.',
            'are you fucking dumb or something? you broke my bot.'
        ]
        log(f"{roastUserOptions[random.randint(0,len(roastUserOptions)-1)]} Full traceback: {e}", "global._osumap")

loginLoop()
bot.run()
