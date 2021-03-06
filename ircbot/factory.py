import contextlib
import logging
import os
import re
import urllib2

from twisted.internet import protocol, reactor

from client import Client


log = logging.getLogger("factory")


try:
    import requests
except ImportError as e:
    log.error("Missing requests library. The translate module won't work.")


# from lxml import html
# from BeautifulSoup import BeautifulSoup as bs


class Factory(protocol.ClientFactory):
    "Factory that creates a client and handles its connection."

    VERSION = "0.3"  # current demibot version
    URL = "https://github.com/mikar/demibot"
    clients = {}
    basedir = os.path.dirname(os.path.realpath(__file__))
    moduledir = os.path.join(basedir, "modules/")

    def __init__(self, network_name, network, configdir, logdir, nologs):
        self.network_name = network_name
        self.network = network
        self.configdir = configdir
        self.logdir = logdir
        # Namespace for modules:
        self.ns = {}
        # Use XOR to set this to False if nologs is True. Could also use
        # not and or is not.
        self.logs_enabled = True ^ nologs
        self.retry_enabled = True  # Retry if connection lost/failed.
        self.quiz_enabled = False
        self.urltitles_enabled = network.get("urltitles_enabled", False)
        self.lost_delay = network.get("lost_delay", 10)
        self.failed_delay = network.get("failed_delay", 30)
        # Set minperms to disable access to commands for certain permission
        # levels. Anything above 0 will disable most public commands.
        self.minperms = network.get("minperms", 0)  # 20 is the maximum.
        if self.minperms:
            log.info("Minperms are set! To enable public commands: .setmin 0")

    def startFactory(self):
        log.info("Starting Factory.")
        self._loadmodules()

    def clientConnectionLost(self, connector, reason):
        "Reconnect after 10 seconds if the connection to the network is lost."
        if self.retry_enabled:
            log.info("Connection lost ({}): reconnecting in {} seconds."
                     .format(reason, self.lost_delay))
            reactor.callLater(self.lost_delay, connector.connect)

    def clientConnectionFailed(self, connector, reason):
        "Reconnect after 30 seconds if the connection to the network fails."
        if self.retry_enabled:
            log.info("Connection failed ({}): reconnecting in {} seconds."
                     .format(reason, self.failed_delay))
            reactor.callLater(self.failed_delay, connector.connect)

    def buildProtocol(self, address):
        log.info("Building protocol for {}.".format(address))
        p = Client(self)
        self.clients[self.network_name] = p
        return p

    def _finalize_modules(self):
        "Call all module finalizers."
        for module in self._findmodules():
            # If rehashing (module already in namespace),
            # finalize the old instance first.
            if module in self.ns:
                if "finalize" in self.ns[module][0]:
                    log.info("Finalize - {}".format(module))
                    self.ns[module][0]["finalize"]()

    def _loadmodules(self):
        "Loads all existing modules."
        self._finalize_modules()
        for module in self._findmodules():
            env = self._getGlobals()
            log.info("Load module - {}".format(module))
            # Load new version of the module
            execfile(os.path.join(self.moduledir, module), env, env)
            # Initialize module
            if "init" in env:
                log.info("initialize module - {}".format(module))
                env["init"](self)
            # Add to namespace so we can find it later
            self.ns[module] = (env, env)

    def _unload_removed_modules(self):
        "Unload all modules removed from the modules directory."
        # Find all modules in namespace that aren't present in moduledir.
        removed_modules = [m for m in self.ns if not m in self._findmodules()]

        for m in removed_modules:
            # Finalize module before deleting it.
            if "finalize" in self.ns[m][0]:
                log.info("Finalize - {}".format(m))
                self.ns[m][0]["finalize"]()
            del self.ns[m]
            log.info("Removed module - {}".format(m))

    def _findmodules(self):
        "Find modules in moduledir."
        modules = [m for m in os.listdir(self.moduledir) if\
                   m.startswith("module_") and m.endswith(".py")]
        return modules

    def _getGlobals(self):
        "Namespace for utilities/methods made available for modules."
        g = {}

        g["get_nick"] = self.get_nick
        g["get_url"] = self.get_url
        g["get_urlinfo"] = self.get_urlinfo
        g["get_title"] = self.get_title
        g["permissions"] = self.permissions
        g["to_utf8"] = self.to_utf8
        g["to_unicode"] = self.to_unicode
        return g

    def get_nick(self, user):
        "Parses nick from nick!user@host."
        return user.split("!", 1)[0]

    def permissions(self, user):
        "Returns the permission level of a user."
        if self.get_nick(user) in self.network["superadmins"]:
                return 20
        elif self.get_nick(user) in self.network["admins"]:
            return 10
        return 0

    def to_utf8(self, _string):
        "Convert string to UTF-8 if it is unicode."
        if isinstance(_string, unicode):
            _string = _string.encode("UTF-8")
        return _string

    def to_unicode(self, _string):
        "Convert string to unicode."
        # NOTE: In python 2 work with unicode. In python 3 stick to str only.
        # http://bit.ly/unipain
        if not isinstance(_string, unicode):
            try:
                _string = unicode(_string)
            except:
                try:
                    _string = _string.decode("utf-8")
                except:
                    _string = _string.decode("iso-8859-1")
        return _string

    def get_url(self, msg):
        "Extracts a URL from a chat message."
        # Does not match www.web.de which is intended.
        # TODO: Improve regex and enable multiple URLs in one message.
        try:
            url = re.search("(?P<url>https?://[^\s]+)", msg).group("url")
        except AttributeError:
            url = None

        return url

    def get_title(self, url):
        "Gets the HTML title of a website."
#         # Three ways to do this. Speed: regex > lxml > beautifulsoup
#         return html.parse(url).find(".//title").text
#         return bs(urllib2.urlopen(url)).title.string
        # Note: http://stackoverflow.com/questions/1732348/regex-match-open-\
        # tags-except-xhtml-self-contained-tags/1732454#1732454
        # Using regex with htmls is usually a bad idea.
        regex = re.compile("<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
        try:
            with contextlib.closing(urllib2.urlopen(url)) as s:
                title = regex.search(s.read()).group(1)
        except (urllib2.HTTPError, AttributeError):
            title = None

        if title:
            return "Title: {}".format(title.strip())


    def get_urlinfo(self, url, nocache=False, params=None, headers=None):
        "Gets data, bs and headers for the given URL."

        # Make this configurable in the config
        browser = "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.11"\
                  "(KHTML, like Gecko) Chrome/23.0.1271.95 Safari/537.11"

        # Common session for all requests.
        s = requests.session()
        s.verify = False
        s.stream = True  # Don't fetch content unless asked.
        s.headers.update({'User-Agent':browser})
        # Custom headers from requester
        if headers:
            s.headers.update(headers)

        try:
            r = s.get(url, params=params)
        except requests.exceptions.InvalidSchema:
            log.error("Invalid schema in URI: {}".format(url))
            return None
        except requests.exceptions.ConnectionError:
            log.error("Connection error when connecting to {}".format(url))
            return None

        size = int(r.headers.get('Content-Length', 0)) // 1024
        # log.debug("Content-Length: %dkB" % size)
        if size > 2048:
            log.warn("Content too large, will not fetch: {}kB {}".format(size,
                                                                         url))
            return None

        return r
