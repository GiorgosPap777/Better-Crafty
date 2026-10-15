import logging
import nh3

from app.classes.web.base_handler import BaseHandler

logger = logging.getLogger(__name__)
auth_log = logging.getLogger("auth")

DEFAULT_LANDING_PAGE = "/panel/dashboard"


class PublicHandler(BaseHandler):
    @staticmethod
    def safe_next_url(next_url: str) -> str:
        """Only allow redirects to local, absolute paths.

        Prevents open redirects such as ``//evil.example`` or ``/\\evil.example``
        while still letting users land back on the page they originally asked for.
        Returns an empty string when the value is not safe to use.
        """
        if not next_url or not isinstance(next_url, str):
            return ""
        if not next_url.startswith("/") or next_url.startswith("//"):
            return ""
        if "\\" in next_url or any(ord(char) < 32 for char in next_url):
            return ""
        # Never bounce back to the auth pages themselves
        if next_url.split("?", 1)[0].rstrip("/") in ("/login", "/logout"):
            return ""
        return next_url

    def get(self, page=None):
        # pylint: disable=no-member
        error = nh3.clean(self.get_argument("error", "Invalid Login!"))
        error_msg = nh3.clean(self.get_argument("error_msg", ""))
        # pylint: enable=no-member

        page_data = {
            "version": self.helper.get_version_string(),
            "error": error,
            "lang": self.helper.get_setting("language"),
            "lang_page": self.helper.get_lang_page(self.helper.get_setting("language")),
            "query": "",
            "background": self.controller.cached_login,
            "brand": self.controller.cached_brand,
            "login_opacity": self.controller.management.get_login_opacity(),
            "themes": self.helper.get_themes(),
            "passkey_enabled": self.controller.passkey.is_enabled(),
        }
        page_data["embed"] = self.get_embed_meta("/login")

        # Only "next" is meaningful here. Anything else is ignored rather than
        # bouncing the user around (and previously crashing the handler).
        page_data["query"] = self.safe_next_url(self.get_query_argument("next", ""))

        # sensible defaults
        template = "public/404.html"

        if page == "login":
            template = "public/login.html"
            current_user = self.get_current_user()
            if current_user and current_user[2].get("enabled"):
                # Already signed in: skip the login form entirely
                self.redirect(page_data["query"] or DEFAULT_LANDING_PAGE)
                return

        elif page == "404":
            template = "public/404.html"

        elif page == "error":
            template = "public/error.html"

        elif page == "offline":
            template = "public/offline.html"

        elif page == "logout":
            exec_user = self.get_current_user()
            self.clear_cookie("token")
            # Delete anti-lockout-user on lockout...it's one time use
            if exec_user and exec_user[2]["username"] == "anti-lockout-user":
                self.controller.users.stop_anti_lockout()
            self.redirect("/login")
            return

        # if we have no page, let's go to login
        else:
            return self.redirect("/login")

        self.render(
            template,
            data=page_data,
            translate=self.translator.translate,
            error_msg=error_msg,
        )

    def post(self, _page=None):
        self.redirect("/login")
