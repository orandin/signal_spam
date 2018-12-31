# Signal spam

This script retrieves spams from your mailbox and reports it to [signal-spam.fr](https://www.signal-spam.fr/)
After reporting, spam is removed from your mailbox automatically.

## Requirements

You must have an account on [Signal Spam](https://www.signal-spam.fr/).

To install the dependencies, please execute :

```bash
pip install -r requirements.txt
```

## Install

Before to launch the script, create the file `config.json` from the file `config.json.default`.

All fields are required excepted "delay" in "mailbox". This field defines the delay below which spams are ignored.
