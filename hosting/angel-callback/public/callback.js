"use strict";

// Registration landing page only: discard any returned credentials without reading them.
// The local application uses SmartAPI's direct PIN/TOTP login, not publisher login.
if (window.location.search || window.location.hash) {
  window.history.replaceState(null, "", window.location.pathname);
}
