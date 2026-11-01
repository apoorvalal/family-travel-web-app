# lalten.org deployment

Public demo: **https://lalten.org/simpsons-travel/**.

The hosted application contains only the fictional Simpsons seed. Everyone shares the same editable demo checklist. The original household application and its documents are not deployed here.

## Layout

- Canonical source: `/root/lalten/apps/simpsons-family-travel/`, vendored from this repository without its Git metadata or runtime state.
- Service definition: `deploy/simpsons-family-travel.service`, symlinked into `/etc/systemd/system/`.
- Public route: the checked-in `nginx-location.conf` block is installed in the existing lalten nginx server block. The trailing slash in `proxy_pass` strips `/simpsons-travel/` before forwarding.
- Backend: `127.0.0.1:8762`, never a public listening socket.
- Persistent fictional state: `/var/lib/simpsons-family-travel/`, managed by systemd `StateDirectory` and kept outside both repositories.

The service uses a dynamic unprivileged user. A read-only bind mount makes canonical app code available as `/app` inside its private mount namespace; `ProtectHome=tmpfs` hides other home directories. The only application writes are to its managed state directory. It starts on boot, restarts after failures, and has bounded memory/task limits. Host Python 3.10+ is sufficient; there is no package installation.

## Updating

1. Run `python3 -B tests.py` in the canonical source repository and commit the new version.
2. Transfer the committed source tree to the canonical server app directory. Do not transfer `.git`, runtime data, caches or credentials. Ensure app files are readable by the service (`chmod -R a+rX` on the app tree).
3. If changed, merge only this app's nginx location block into the existing server configuration; do not replace the site's entire configuration.
4. Keep the unit as a symlink to the canonical copy, run `systemctl daemon-reload`, then `systemctl restart simpsons-family-travel`.
5. Run `nginx -t` before `systemctl reload nginx` whenever proxy configuration changes.
6. Check `/simpsons-travel/health`, all static assets, the state API, a PDF download, and a same-origin checklist mutation. Confirm shared browser updates and that existing site routes still respond.
7. Commit the app source/config/docs changes in the lalten deployment repository. Preserve unrelated working-tree changes there.

A code update or ordinary restart does not reset the demo checklist. To prepare a clean demo intentionally, stop the service and archive the state directory before initializing new data. No automatic reset job is installed.

## Operations

```sh
systemctl status simpsons-family-travel
journalctl -u simpsons-family-travel -n 40 --no-pager
systemctl restart simpsons-family-travel
curl --fail https://lalten.org/simpsons-travel/health
```

The website is public; the source repository can remain private. No GitHub credentials, real family data or personal document archive are required by the service.
