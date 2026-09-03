# SETUP — read this first

This project is published at https://github.com/shashankagrawal24/indiafd.
GitHub Actions runs the collector every Monday at 06:30 IST and commits changed
rates back to the repository.

---

## The short way

From inside this folder:

```bash
bash push_to_github.sh
```

It checks for the usual problems first, asks before overwriting, pushes, and
prints the two browser steps that follow. If it stops with an error, the error
tells you what to fix.

---

## The manual way

```bash
cd india-fd-rates          # the folder this file is in
git init -b main
git remote add origin https://github.com/shashankagrawal24/indiafd.git
git add -A
git commit -m "init: weekly Indian bank FD rate collector"
git push -u origin main
```

If the push asks for a password, GitHub no longer accepts your account password.
Install the GitHub CLI and sign in once:

```bash
brew install gh          # macOS.  Windows: winget install GitHub.cli
gh auth login            # GitHub.com -> HTTPS -> login with a web browser
```

Then run the push again.

---

## Check the unzip did not lose anything

The most common silent failure. `.github` starts with a dot, so Finder and
Explorer hide it, and some unzip tools drop it.

```bash
ls -a                              # .github should be listed
ls .github/workflows               # weekly.yml and tests.yml should both exist
```

If `.github` is missing, extract the archive from the command line instead of
double-clicking it:

```bash
unzip -o india-fd-rates.zip
```

No `.github/workflows/weekly.yml` means no schedule, and the repo will sit there
doing nothing even though everything else looks fine.

---

## After the push

1. **Let Actions write.** https://github.com/shashankagrawal24/indiafd/settings/actions
   → Workflow permissions → **Read and write permissions** → Save.
   Skipping this gives you a green run that commits nothing.

2. **Run it once by hand.** https://github.com/shashankagrawal24/indiafd/actions
   → "Weekly FD rates" → Run workflow. It takes 10–20 minutes, because the
   scraper pauses three seconds between requests to each bank.

3. **Read the Summary** on the finished run. It shows how many of the 49
   eligible banks returned rates, then a table of the ones that need checking by
   hand, each with a link.

Expect partial coverage on the first run. GitHub's runners are US datacenter
machines and several Indian bank firewalls refuse them. That is recorded as
`status=blocked`, not hidden.

---

## If you cannot get git working at all

You can create the two workflow files through the GitHub website. On the repo
page choose **Add file → Create new file**, and type this as the filename:

```
.github/workflows/weekly.yml
```

Typing the slashes creates the folders. Paste the contents of
`.github/workflows/weekly.yml` from this folder, and commit. Repeat for
`tests.yml`. Then upload the rest of the folders with **Add file → Upload
files**, dragging `src`, `tests` and `data` in.

This works, but it is slower and easy to get half-done. The script is better.

---

## Running it on your own machine first

Optional, and the quickest way to see real numbers, since your home connection
is an Indian IP and will not be refused the way GitHub's runners are:

```bash
pip install -e ".[dev]"
pytest -q                                   # 37 offline tests
python -m fdrates run --limit 5 --verbose   # five banks, live
```
