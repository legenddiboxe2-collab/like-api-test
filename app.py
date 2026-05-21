from flask import Flask, request, jsonify
import asyncio
import json
import binascii
import requests
import aiohttp
import urllib3
import traceback

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
from google.protobuf.message import DecodeError

import like_pb2
import like_count_pb2
import uid_generator_pb2

from config import URLS_INFO, URLS_LIKE, FILES

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

app = Flask(__name__)

def load_tokens(server):

    filename = FILES.get(
        server,
        "token_bd.json"
    )

    with open(f"tokens/{filename}", "r") as f:
        return json.load(f)

def get_headers(token):

    return {

        "User-Agent":
        "Dalvik/2.1.0 (Linux; U; Android 9)",

        "Connection":
        "Keep-Alive",

        "Accept-Encoding":
        "gzip",

        "Authorization":
        f"Bearer {token}",

        "Content-Type":
        "application/x-www-form-urlencoded",

        "Expect":
        "100-continue",

        "X-Unity-Version":
        "2018.4.11f1",

        "X-GA":
        "v1 1",

        "ReleaseVersion":
        "OB53",
    }

def encrypt_message(data):

    cipher = AES.new(
        b'Yg&tc%DEuh6%Zc^8',
        AES.MODE_CBC,
        b'6oyZDr22E3ychjM%'
    )

    return binascii.hexlify(
        cipher.encrypt(
            pad(data, AES.block_size)
        )
    ).decode()

def create_like(uid, region):

    m = like_pb2.like()

    m.uid = int(uid)

    m.region = region

    return m.SerializeToString()

def create_uid(uid):

    m = uid_generator_pb2.uid_generator()

    m.saturn_ = int(uid)

    m.garena = 1

    return m.SerializeToString()

async def send(token, url, data):

    headers = get_headers(token)

    async with aiohttp.ClientSession() as s:

        async with s.post(
            url,
            data=bytes.fromhex(data),
            headers=headers
        ) as r:

            if r.status == 200:
                return await r.text()

            return None

async def multi(uid, server, url):

    enc = encrypt_message(
        create_like(uid, server)
    )

    tokens = load_tokens(server)

    tasks = [

        send(
            tokens[i % len(tokens)]["token"],
            url,
            enc
        )

        for i in range(20)

    ]

    return await asyncio.gather(*tasks)

def get_info(enc, server, token):

    url = URLS_INFO.get(
        server,
        "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"
    )

    r = requests.post(
        url,
        data=bytes.fromhex(enc),
        headers=get_headers(token),
        verify=False,
        timeout=20
    )

    try:

        p = like_count_pb2.Info()

        p.ParseFromString(r.content)

        return p

    except DecodeError:

        return None

@app.route("/")
def home():

    return jsonify({

        "status": "online",

        "message": "Railway Like API Running"

    })

@app.route("/like")
def like():

    try:

        uid = request.args.get("uid")

        server = request.args.get(
            "server",
            ""
        ).upper()

        if not uid or not server:

            return jsonify({

                "error":
                "UID and server required"

            }), 400

        tokens = load_tokens(server)

        enc = encrypt_message(
            create_uid(uid)
        )

        before = None
        tok = None

        for t in tokens[:5]:

            before = get_info(
                enc,
                server,
                t["token"]
            )

            if before:

                tok = t["token"]

                break

        if not before:

            return jsonify({

                "error":
                "Player not found"

            }), 500

        before_json = json.loads(
            MessageToJson(before)
        )

        before_like = int(

            before_json.get(
                "AccountInfo",
                {}
            ).get(
                "Likes",
                0
            )

        )

        like_url = URLS_LIKE.get(
            server,
            "https://clientbp.ggblueshark.com/LikeProfile"
        )

        loop = asyncio.new_event_loop()

        asyncio.set_event_loop(loop)

        loop.run_until_complete(

            multi(
                uid,
                server,
                like_url
            )

        )

        loop.close()

        after_proto = get_info(
            enc,
            server,
            tok
        )

        after = json.loads(
            MessageToJson(after_proto)
        )

        after_like = int(

            after.get(
                "AccountInfo",
                {}
            ).get(
                "Likes",
                0
            )

        )

        return jsonify({

            "status": 1,

            "credits":
            "great.thug4ff.com",

            "uid":
            after.get(
                "AccountInfo",
                {}
            ).get(
                "UID",
                0
            ),

            "player":
            after.get(
                "AccountInfo",
                {}
            ).get(
                "PlayerNickname",
                ""
            ),

            "likes_before":
            before_like,

            "likes_after":
            after_like,

            "likes_added":
            after_like - before_like

        })

    except Exception as e:

        return jsonify({

            "error": str(e),

            "trace": traceback.format_exc()

        }), 500
