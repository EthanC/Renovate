import json
from datetime import datetime
from sys import exit, stderr
from typing import Any, Dict, Optional

from loguru import logger
from notifiers.logging import NotificationHandler

from utils import Utility


class Renovate:
    """
    Renovate is a PlayStation title watcher that reports updates via Discord.

    https://github.com/EthanC/Renovate
    """

    def Initialize(self: Any) -> None:
        """Initialize Renovate and begin primary functionality."""

        logger.info("Renovate")
        logger.info("https://github.com/EthanC/Renovate")

        self.config: Dict[str, Any] = Renovate.LoadConfig(self)

        Renovate.SetupLogging(self)

        self.history: Dict[str, Any] = Renovate.LoadHistory(self)
        self.changed: bool = False

        # Battle.net
        for title in self.config["titles"]["battle"]:
            Renovate.ProcessBattleTitle(self, title)

        # PlayStation 5
        for title in self.config["titles"]["prospero"]:
            Renovate.ProcessProsperoTitle(self, title)

        if self.changed is True:
            Renovate.SaveHistory(self)

        logger.success("Finished processing titles")

    def LoadConfig(self: Any) -> Dict[str, Any]:
        """Load the configuration values specified in config.json"""

        try:
            with open("config.json", "r") as file:
                config: Dict[str, Any] = json.loads(file.read())
        except Exception as e:
            logger.critical(f"Failed to load configuration, {e}")

            exit(1)

        logger.success("Loaded configuration")

        return config

    def SetupLogging(self: Any) -> None:
        """Setup the logger using the configured values."""

        settings: Dict[str, Any] = self.config["logging"]

        if (level := settings["severity"].upper()) != "DEBUG":
            try:
                logger.remove()
                logger.add(stderr, level=level)

                logger.success(f"Set logger severity to {level}")
            except Exception as e:
                # Fallback to default logger settings
                logger.add(stderr, level="DEBUG")

                logger.error(f"Failed to set logger severity to {level}, {e}")

        if settings["discord"]["enable"] is True:
            level: str = settings["discord"]["severity"].upper()
            url: str = settings["discord"]["webhookUrl"]

            try:
                # Notifiers library does not natively support Discord at
                # this time. However, Discord will accept payloads which
                # are compatible with Slack by appending to the url.
                # https://github.com/liiight/notifiers/issues/400
                handler: NotificationHandler = NotificationHandler(
                    "slack", defaults={"webhook_url": f"{url}/slack"}
                )

                logger.add(
                    handler,
                    level=level,
                    format="```\n{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}\n```",
                )

                logger.success(f"Enabled logging to Discord with severity {level}")
            except Exception as e:
                logger.error(f"Failed to enable logging to Discord, {e}")

    def LoadHistory(self: Any) -> Dict[str, Any]:
        """Load the last seen title versions specified in history.json"""

        try:
            with open("history.json", "r") as file:
                history: Dict[str, Any] = json.loads(file.read())
        except FileNotFoundError:
            history: Dict[str, Any] = {"battle": {}, "prospero": {}}

            logger.success("Title history not found, created empty file")
        except Exception as e:
            logger.critical(f"Failed to load title history, {e}")

            exit(1)

        if history.get("battle") is None:
            history["battle"] = {}

        if history.get("prospero") is None:
            history["prospero"] = {}

        logger.success("Loaded title history")

        return history

    def ProcessBattleTitle(self: Any, title: Dict[str, str]) -> None:
        """
        Get the current version of the specified Battle.net title and
        determine whether or not it has updated.
        """

        titleId: str = title["titleId"]
        region: str = title["region"]

        past: Optional[str] = self.history["battle"].get(titleId)

        data: Optional[Dict[str, Any]] = Utility.GET(
            self, f"https://blizztrack.com/api/manifest/versions/{titleId}"
        )

        if data is None:
            return

        titleId = data["product"]
        name: str = data["name"]
        current: str = data["data"][0]["versionsname"]
        build: str = data["data"][0]["buildconfig"]

        # Try to select desired region, otherwise default to first
        for entry in data["data"]:
            if entry["region_name"].lower() == region.lower():
                region = entry["region_name"]
                current = entry["versionsname"]
                build = entry["buildconfig"]

        if past is None:
            self.history["battle"][titleId] = current
            self.changed = True

            logger.success(
                f"Battle.net title {name} previously untracked, saved version {current} to title history"
            )

            return
        elif past == current:
            logger.info(f"Battle.net title {name} not updated ({current})")

            return

        logger.success(f"Battle.net title {name} updated, {past} -> {current}")

        thumbnail: Optional[str] = None
        for image in data["logos"]:
            if image["type"] == "image/png":
                thumbnail = image["url"]

                break

        success: bool = Renovate.Notify(
            self,
            {
                "name": name,
                "url": f"https://blizztrack.com/v/{titleId}/versions",
                "timestamp": data["indexed"],
                "platformColor": "148EFF",
                "region": region,
                "titleId": titleId,
                "platformLogo": "https://i.imgur.com/dI6bDr7.png",
                "thumbnail": thumbnail,
                "pastVersion": past,
                "currentVersion": current,
                "build": None
                if data["encrypted"] is True
                else Utility.GetBattleBuild(self, titleId, region, build),
            },
        )

        # Ensure no changes go without notification
        if success is True:
            self.history["battle"][titleId] = current
            self.changed = True

    def ProcessProsperoTitle(self: Any, titleId: str) -> None:
        """
        Get the current version of the specified PlayStation 5 title and
        determine whether or not it has updated.
        """

        past: Optional[str] = self.history["prospero"].get(titleId)

        data: Optional[Dict[str, Any]] = Utility.GET(
            self, f"https://prosperopatches.com/api/lookup?titleid={titleId}"
        )

        if (data is None) or (data["success"] is False):
            return

        name: str = data["metadata"]["name"]
        current: str = data["metadata"]["currentVersion"]

        if past is None:
            self.history["prospero"][titleId] = current
            self.changed = True

            logger.success(
                f"Prospero title {name} previously untracked, saved version {current} to title history"
            )

            return
        elif past == current:
            logger.info(f"Prospero title {name} not updated ({current})")

            return

        logger.success(f"Prospero title {name} updated, {past} -> {current}")

        success: bool = Renovate.Notify(
            self,
            {
                "name": name,
                "url": f"https://prosperopatches.com/{titleId}",
                "platformColor": "00439C",
                "region": data["metadata"]["region"],
                "titleId": titleId,
                "platformLogo": "https://i.imgur.com/ccNqLcb.png",
                "thumbnail": data["metadata"]["icon"],
                "image": data["metadata"]["background"],
                "pastVersion": past,
                "currentVersion": current,
            },
        )

        # Ensure no changes go without notification
        if success is True:
            self.history["prospero"][titleId] = current
            self.changed = True

    def Notify(self: Any, data: Dict[str, str]) -> bool:
        """Report title version change to the configured Discord webhook."""

        settings: Dict[str, Any] = self.config["discord"]

        region: str = data["region"]
        titleId: str = data["titleId"]

        payload: Dict[str, Any] = {
            "username": settings["username"],
            "avatar_url": settings["avatarUrl"],
            "embeds": [
                {
                    "title": data["name"],
                    "url": data.get("url"),
                    "timestamp": datetime.utcnow().isoformat()
                    if (timestamp := data.get("timestamp")) is None
                    else timestamp,
                    "color": int(data["platformColor"], base=16),
                    "footer": {
                        "text": f"({region}) {titleId}",
                        "icon_url": data["platformLogo"],
                    },
                    "thumbnail": {"url": data.get("thumbnail")},
                    "image": {"url": data.get("image")},
                    "author": {
                        "name": "Renovate",
                        "url": "https://github.com/EthanC/Renovate",
                        "icon_url": "https://i.imgur.com/bNGKmG0.png",
                    },
                    "fields": [
                        {
                            "name": "Past Version",
                            "value": data["pastVersion"],
                            "inline": True,
                        },
                        {
                            "name": "Current Version",
                            "value": data["currentVersion"],
                            "inline": True,
                        },
                    ],
                }
            ],
        }

        if (build := data.get("build")) is not None:
            payload["embeds"][0]["fields"].append(
                {"name": "Build Name", "value": f"`{build}`"}
            )

        return Utility.POST(self, settings["webhookUrl"], payload)

    def SaveHistory(self: Any) -> None:
        """Save the latest title versions to history.json"""

        if self.config.get("debug") is True:
            logger.warning("Debug is active, not saving title history")

            return

        try:
            with open("history.json", "w+") as file:
                file.write(json.dumps(self.history, indent=4))
        except Exception as e:
            logger.critical(f"Failed to save title history, {e}")

            exit(1)

        logger.success("Saved title history")


if __name__ == "__main__":
    try:
        Renovate.Initialize(Renovate)
    except KeyboardInterrupt:
        exit()
