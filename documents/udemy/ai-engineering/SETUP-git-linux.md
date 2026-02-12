# Setting Up Git on Linux

## Step 1: Install Git

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install git
```

**Fedora:**

```bash
sudo dnf install git
```

**Arch:**

```bash
sudo pacman -S git
```

## Step 2: Verify Installation

```bash
git --version
```

## Step 3: Configure Your Identity

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

## Step 4: Set Default Branch Name

```bash
git config --global init.defaultBranch main
```

## Step 5: Generate an SSH Key (for GitHub/GitLab)

```bash
ssh-keygen -t ed25519 -C "your.email@example.com"
```

Press Enter to accept the default file location, then set a passphrase (or leave empty).

Start the SSH agent and add the key:

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

Copy the public key:

```bash
cat ~/.ssh/id_ed25519.pub
```

Add this key to your GitHub account under **Settings > SSH and GPG keys > New SSH key**.

## Step 6: Test the Connection

```bash
ssh -T git@github.com
```

You should see: `Hi <username>! You've successfully authenticated`.

## Step 7: Clone a Repository

```bash
git clone git@github.com:username/repo.git
```

## Common Git Commands

| Command | Description |
|---|---|
| `git status` | Show working tree status |
| `git add .` | Stage all changes |
| `git commit -m "message"` | Commit staged changes |
| `git push` | Push commits to remote |
| `git pull` | Fetch and merge remote changes |
| `git log --oneline` | View commit history |
