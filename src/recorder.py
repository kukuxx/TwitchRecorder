import os
import datetime
import asyncio

import aiohttp
import requests

from asyncio.subprocess import Process


class TwitchRecord:

    def __init__(self, client_id, client_secret, channel_list, logger, token):
        self.logger = logger
        self._client_id = client_id
        self._client_secret = client_secret
        self._channel_list = channel_list
        self._access_token = token

        self.check_path()
        self._streamername: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._lock_p = asyncio.Lock()
        self._copy_list = []
        self._process = []
        self._check = True
        self._done = False
        self._add = False
        self._token_status = True
        self._token_url = (
            f"https://id.twitch.tv/oauth2/token?client_id={self._client_id}"
            f"&client_secret={self._client_secret}&grant_type=client_credentials"
        )
        self._apiurl = f"https://api.twitch.tv/helix/streams"

    def check_path(self):
        self.ffmpegpath = os.path.join(os.path.dirname(__file__), "..", "dep", "ffmpeg.exe")
        self.streamlinkpath = os.path.join(os.path.dirname(__file__), "..", "dep", "streamlink.exe")
        self._output_dir = "downloads"
        if not os.path.exists(self._output_dir):
            os.makedirs(self._output_dir)
        if not os.path.exists(self.ffmpegpath):
            self.logger.error("FFmpeg not found; recording cannot start.")
        if not os.path.exists(self.streamlinkpath):
            self.logger.error("Streamlink not found; recording cannot start.")

    def stop_check(self):
        self._check = False

    async def get_token(self):
        """取得token"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self._token_url, timeout=15) as response:
                    response.raise_for_status()
                    data = await response.json()
                    new_token = data["access_token"]
                    self._token_status = True
                    self._access_token = new_token
                    self.logger.info(f"Get Token Successful: {new_token}")
                    return new_token

        except requests.exceptions.HTTPError as e:
            self._token_status = False
            self.logger.error(f"Failed to Obtain Token: {e}")
        except requests.exceptions.Timeout as e:
            self._token_status = False
            self.logger.error(f"Timeout For Obtain Token: {e}")
        except Exception as e:
            self._token_status = False
            self.logger.exception(f"Failed to Obtain Token: {e}")

    async def check(self, channel):
        """確認streamer狀態"""
        try:
            headers = {
                "Client-ID": self._client_id,
                "Authorization": f"Bearer {self._access_token}"
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._apiurl + f"?user_login={channel}", headers=headers, timeout=15
                ) as r:
                    r.raise_for_status()
                    info = await r.json()
                    if info["data"]:
                        streamername = info["data"][0]["user_name"]
                        self._streamername.update({channel: streamername})
                        return True
                    else:
                        return False

        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                self.logger.warning("Token Invalid")
                self._access_token = None
                self._token_status = False
                return False
            elif e.status == 404:
                self.logger.error(f"Channel Not Found: {e}")
                return False
            else:
                self.logger.error(f"Client Response Error: {e}")
                return False
        except asyncio.TimeoutError:
            self.logger.warning("Query Timeout")
            return False
        except Exception as e:
            self.logger.exception(f"Query Error: {e}")
            return False

    async def loop_check(self):
        """建立迴圈重複確認"""
        try:
            self.logger.info("Start Running")
            self._copy_list = self._channel_list.copy()
            self.logger.info(f"{self._channel_list}:Start Monitoring")

            while self._check:
                if self._access_token is None or not self._token_status:
                    await self.get_token()

                if self._token_status:
                    async with self._lock:
                        if self._add:
                            self.logger.info(f"{self._channel_list}:Start Monitoring")
                            self._add = False
                            self._copy_list = self._channel_list.copy()

                    if self._copy_list and self._check:
                        tasks = [
                            asyncio.create_task(self.check(channel)) for channel in self._copy_list
                        ]
                        results = await asyncio.gather(*tasks)
                        online_channel = [
                            self._copy_list[i] for i, result in enumerate(results) if result
                        ]
                        if online_channel and self._check:
                            channels_to_remove = []
                            for _channel in online_channel:
                                asyncio.create_task(self.record_channel(_channel))  # 建立錄製
                                channels_to_remove.append(_channel)

                            async with self._lock:
                                for remove_channel in channels_to_remove:  # 將上線的streamer取出list
                                    self._channel_list.remove(remove_channel)
                                self._copy_list = self._channel_list.copy()

                    if self._check:
                        await asyncio.sleep(10 if online_channel else 3)
                    else:
                        break
                else:
                    self.logger.error(
                        "Please check if the Client ID & SECRET are correct and Stop Record"
                    )
                    await asyncio.sleep(1)

            self.logger.info("Stop running")
            self.logger.info("The file has been saved, and Can be closed.")
            self._done = True

        except Exception as e:
            self.logger.exception(f" Loop Check Error: {e}")
            return

    async def record_channel(self, channel):
        """呼叫streamlink和ffmpeg開始錄製"""
        name = self._streamername.get(channel, channel)
        filename = f"{name} - Twitch {datetime.datetime.now().strftime('%Y-%m-%d %H_%M_%S')}.mp4"
        filepath = os.path.join(self._output_dir, filename)
        create_no_window = 0x08000000

        try:  # 建立錄製子進程
            self.logger.info(f"{channel} Start recording")
            proc: Process = await asyncio.create_subprocess_exec(
                self.streamlinkpath,
                "--twitch-disable-ads",
                "--ffmpeg-ffmpeg",
                self.ffmpegpath,
                f"twitch.tv/{channel}",
                "best",
                "-o",
                filepath,
                creationflags=create_no_window,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                text=False
            )
            async with self._lock_p:
                self._process.append(proc)

            stdout, stderr = await proc.communicate()
            if proc.returncode != 0 and stderr:
                self.logger.error(f"Recording Error Output: {stderr.decode('utf-8')}")

            self.logger.info(f"{channel}:Recording Stream is Done")

        except Exception as e:
            self.logger.exception(f"Error: {e}")
        finally:
            async with self._lock:
                self._channel_list.append(channel)
                self._add = True
            async with self._lock_p:
                if self._process:
                    self._process.remove(proc)

    async def close_process(self):
        if self._process:
            async with self._lock_p:
                for process in self._process:
                    try:
                        process.terminate()  # 終止 streamlink 錄製
                        await asyncio.wait_for(process.wait(), timeout=5)  # 等待進程終止
                        self.logger.info("Stop Recording")
                    except asyncio.TimeoutError:
                        process.kill()
                    except ProcessLookupError:
                        self.logger.warning("Process already exited, cannot terminate")
                        pass
                    except Exception as e:
                        self.logger.exception(f"Close Process Error: {e}")
