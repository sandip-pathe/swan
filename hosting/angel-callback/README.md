# Angel One registration landing page

This package contains only three public static assets. It does not publish the trading application, backend, Firebase browser configuration or secrets. It is a registration landing page, not an implemented publisher-login token exchange. The local app still uses private PIN/TOTP login for market data.

## Deploy using Firebase Cloud Shell

1. Open project `studio-4445763718-d07db` in Firebase Console and open Cloud Shell.
2. Upload `swan-angel-callback.zip` through Cloud Shell's upload menu.
3. Run:

```bash
unzip -o swan-angel-callback.zip -d swan-angel-callback
cd swan-angel-callback
firebase deploy --only hosting --project studio-4445763718-d07db --config firebase.json
```

No local CLI installation is required. Cloud Shell provides Firebase CLI and Google authentication. If prompted to authorize Cloud Shell, use the account owning this project. Do not run `firebase init` or upload the whole repository.

The command replaces the Hosting content of site `studio-4445763718-d07db` with this small landing page; it does not merge with other hosted pages. The site returned Firebase's Site Not Found page when checked before packaging. If you have since published another site there, stop and choose a separate Hosting site first. Firebase Authentication users/settings are not changed by this Hosting-only deployment.

## After deployment

Open this exact address and confirm it displays **Registration page ready.**:

```text
https://studio-4445763718-d07db.web.app/angelone/callback
```

Then paste that exact address into Angel One's **Redirect URL** field. Leave the optional postback URL empty; the app does not accept broker order webhooks. Angel One still requires the actual permitted primary static IP and may apply additional app/domain validation. Hosting does not supply or fix the outbound static IP of the locally running market-data client.

The landing page removes query/fragment values from the visible browser history, loads no third-party resources and makes no token exchange requests. The initial HTTPS request necessarily reaches Firebase Hosting; browser cleanup does not prevent hosting infrastructure from processing its URL. Do not use publisher-login flows with this landing page as a production authentication callback.

The target address is not live until deployment succeeds. This package has not been published or browser-tested. It requires no private credentials in its files.
