# /backend/app/plugins/security/waf.py
from fastapi import Request, HTTPException
import re
from urllib.parse import unquote
from aiohttp import ClientSession
import logging
from fastapi.responses import JSONResponse

class WAFActions:
    BLOCK = "block"
    LOG = "log"
    CAPTCHA = "captcha"

class ThreatIntelFeed:
    def __init__(self, config):
        self.feeds = config.feeds if hasattr(config, 'feeds') else []
        self.blocked_ips = set()
        self.update_interval = config.update_interval if hasattr(config, 'update_interval') else 3600

    async def update_feeds(self):
        async with ClientSession() as session:
            for feed_url in self.feeds:
                try:
                    async with session.get(feed_url) as response:
                        ips = await response.text()
                        self._process_ips(ips)
                except Exception as e:
                    print(f"Error updating threat feed {feed_url}: {str(e)}")

    def _process_ips(self, raw_ips):
        new_ips = set()
        for line in raw_ips.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                new_ips.add(line.split()[0])  # Extract IP
        self.blocked_ips.update(new_ips)

class WebApplicationFirewall:
    def __init__(self, config: dict, intel_feed: ThreatIntelFeed):
        self.rules = self._compile_rules(config.rules if hasattr(config, 'rules') else [])
        self.mode = config.mode if hasattr(config, 'mode') else 'block'
        self.rate_limiter = {}
        self.intel_feed = intel_feed
        self.config = config

    def _compile_rules(self, rules):
        compiled = []
        for rule in rules:
            pattern = re.compile(rule.pattern, re.IGNORECASE)
            compiled.append((pattern, rule.action))
        return compiled

    async def inspect_request(self, request: Request):

        # Check for honeypot/deception traps
        try:
            if hasattr(self, 'config') and hasattr(self.config, 'deception') and hasattr(self.config.deception, 'traps'):
                if any(re.match(trap["path"], request.url.path) for trap in self.config.deception.traps):
                    client_ip = request.client.host
                    await self._apply_action("log", client_ip, request)
                    return JSONResponse(
                        status_code=418,
                        content={"detail": "I'm a teapot"},
                        headers={"X-Deception-Trap": "Triggered"}
                    )
        except Exception as e:
            # Log the error but continue with the inspection
            logging.error(f"Error in deception traps check: {str(e)}")

        # Check blocked IPs first
        client_ip = request.client.host
        if client_ip in self.intel_feed.blocked_ips:
            await self._apply_action("block", client_ip, request)
            return False
        
        # Check for suspicious patterns
        path = unquote(request.url.path)
        query = unquote(str(request.query_params))
        body = await request.body()
        
        # Vérification des patterns dangereux
        for pattern, action in self.rules:
            if (pattern.search(path) or 
                pattern.search(query) or 
                pattern.search(body.decode(errors='ignore'))):
                await self._apply_action(action, client_ip, request)
                return False
        return True

    async def _apply_action(self, action, ip, request):
        if action == WAFActions.BLOCK:
            raise HTTPException(403, "Request blocked by WAF")
        elif action == WAFActions.LOG:
            request.app.state.logger.warn(f"Attempted WAF attack detected - IP: {ip}")
        elif action == WAFActions.CAPTCHA:
            request.state.require_captcha = True

    async def __call__(self, request: Request, call_next):
        if not await self.inspect_request(request):
            return JSONResponse(
                status_code=403,
                content={"detail": "Access denied by WAF"}
            )
        return await call_next(request)