import json
import logging
from datetime import datetime
from os import environ
from sys import exit
from typing import Any, Dict, Self

import dotenv
from discord_webhook import DiscordEmbed, DiscordWebhook
from loguru import logger
from notifiers.logging import NotificationHandler

from handlers import Intercept
from services import Battlenet, Orbis, Prospero, Steam


class Renovate:
    """
    Renovate is a Steam, Battle.net, and PlayStation title watcher that
    reports updates via Discord.

    https://github.com/EthanC/Renovate
    """

    def Start(self: Self) -> None:
        """Initialize Renovate and begin primary functionality."""

        logger.info("Renovate")
        logger.info("https://github.com/EthanC/Renovate")

        if dotenv.load_dotenv():
            logger.success("Loaded environment variables")
            logger.trace(environ)

        # Reroute standard logging to Loguru
        logging.basicConfig(handlers=[Intercept()], level=0, force=True)

        if logUrl := environ.get("DISCORD_LOG_WEBHOOK"):
            if not (logLevel := environ.get("DISCORD_LOG_LEVEL")):
                logger.critical("Level for Discord webhook logging is not set")

                return

            logger.add(
                NotificationHandler(
                    "slack", defaults={"webhook_url": f"{logUrl}/slack"}
                ),
                level=logLevel,
                format="```\n{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}\n```",
            )

            logger.success(f"Enabled logging to Discord webhook")
            logger.trace(logUrl)

        self.history: Dict[str, Any] = Renovate.LoadHistory(self)
        self.changed: bool = False

        # Steam
        if titles := environ.get("STEAM_TITLES"):
            for title in titles.split(","):
                if result := Steam.IsUpdated(self, title):
                    Renovate.Notify(self, result)

        # Battle.net
        if titles := environ.get("BATTLE_TITLES"):
            for title in titles.split(","):
                if result := Battlenet.IsUpdated(self, title):
                    Renovate.Notify(self, result)

        # PlayStation 5
        if titles := environ.get("PROSPERO_TITLES"):
            for title in titles.split(","):
                if result := Prospero.IsUpdated(self, title):
                    Renovate.Notify(self, result)

        # PlayStation 4
        if titles := environ.get("ORBIS_TITLES"):
            for title in titles.split(","):
                if result := Orbis.IsUpdated(self, title):
                    Renovate.Notify(self, result)

        if self.changed:
            Renovate.SaveHistory(self)

        logger.success("Finished processing titles")

    def LoadHistory(self: Self) -> Dict[str, Any]:
        """Load the last seen title versions specified in history.json"""

        try:
            with open("history.json", "r") as file:
                history: Dict[str, Any] = json.loads(file.read())
        except FileNotFoundError:
            history: Dict[str, Any] = {
                "steam": {},
                "battle": {},
                "prospero": {},
                "orbis": {},
            }

            with open("history.json", "w+") as file:
                file.write(json.dumps(history, indent=4))

            logger.success("Title history not found, created empty file")
        except Exception as e:
            logger.critical(f"Failed to load title history, {e}")

            exit(1)

        if not history.get("steam"):
            history["steam"] = {}

        if not history.get("battle"):
            history["battle"] = {}

        if not history.get("prospero"):
            history["prospero"] = {}

        if not history.get("orbis"):
            history["orbis"] = {}

        logger.success("Loaded title history")

        return history

    def SaveHistory(self: Self) -> None:
        """Save the latest title versions to history.json"""

        if environ.get("DEBUG"):
            logger.warning("Debug is active, not saving title history")

            return

        try:
            with open("history.json", "w+") as file:
                file.write(json.dumps(self.history, indent=4))
        except Exception as e:
            logger.critical(f"Failed to save title history, {e}")

            exit(1)

        logger.success("Saved title history")

    def Notify(self: Self, embed: DiscordEmbed) -> None:
        """Report title version change to the configured Discord webhook."""

        if not (url := environ.get("DISCORD_NOTIFY_WEBHOOK")):
            logger.info("Discord webhook for notifications is not set")

            return

        embed.set_author(
            "Renovate",
            url="https://github.com/EthanC/Renovate",
            icon_url="https://i.imgur.com/bNGKmG0.png",
        )

        if not embed.timestamp:
            embed.set_timestamp(datetime.now().timestamp())

        DiscordWebhook(url=url, embeds=[embed], rate_limit_retry=True).execute()


if __name__ == "__main__":
    try:
        Renovate.Start(Renovate)
    except KeyboardInterrupt:
        exit()
