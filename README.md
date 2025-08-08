# firefly-gaf

[Firefly III](https://github.com/firefly-iii/) is an amazing tool to manage personal finances.  And its [data importer](https://github.com/firefly-iii/data-importer) is a bliss to import transactions automatically via third party services.

When transactions are made using via some payment providers, such as VISA, the IBAN of the beneficiary might be an intermediate account that doesn't reflect the business you made the payment to.  When the data importer imports these transactions, the IBAN is the most strict reference for the destination bank account, and therefore many different business will be grouped under the same IBAN.  This is not very convenient, but of course there is a way around that.

**The workaround** is a two steps approach:
1. Modify the name of the "generic" bank account that groups all of the mislabelled transactions.  From now on, the data importer will add a note to the transactions added to this account, inserting the original beneficiary name.
2. For each beneficiary ending up in this account, create a rule that matches the note, and changes the beneficiary to an account named more appropriately.

This first step can not really be automated, as only you, as a human, remembering where you made the passed transactions, can know that the current destination account of some transactions is wrong.

The second step however is pretty easy to handle, and this is precisely what this repo aims to do.

This tool is a simple script, that can run on demand or periodically (see systemd deployment).  It is packaged in a container for easy distribution and installation.

## Run from source

**Requirements**:
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

```console
$ git clone https://github.com/edvgui/firefly-gaf.git
$ ./firefly-gaf/script.py
Usage: script.py [OPTIONS] ACCOUNT
Try 'script.py --help' for help.

Error: Missing argument 'ACCOUNT'
```

## Run with podman

**Requirements**:
- podman or docker

```console
$ podman run --rm ghcr.io/edvgui/firefly-gaf:latest
Usage: script.py [OPTIONS] ACCOUNT
Try 'script.py --help' for help.

Error: Missing argument 'ACCOUNT'
```

## Run periodically with systemd timer

**Requirements**:
- podman
- [quadlet](https://docs.podman.io/en/latest/markdown/podman-quadlet-install.1.html)

1. Create a container unit named `firefly-gaf.container` in the folder `.config/containers/systemd/` of your user with the following content:
```systemd
[Unit]
Description=Podman firefly-gaf.service
Documentation=https://github.com/edvgui/firefly-gaf
Wants=firefly-gaf.timer
PartOf=firefly-gaf.timer

[Install]
WantedBy=default.target

[Container]
Image=ghcr.io/edvgui/firefly-gaf:latest
Environment=FIREFLY_III_URL=https://your-firefly-instance/
Environment=FIREFLY_III_ACCESS_TOKEN=...
Environment=FIREFLY_III_RULE_GROUP=an-existing-rule-group-name
Environment=ACCOUNT_NAME=Visa
```

2. Create a timer unit named `firefly-gaf.timer` in the folder `.config/systemd/user/` of your user with the following content:
```systemd
[Unit]
Description=Podman firefly-gaf.timer
Documentation=https://github.com/edvgui/firefly-gaf
Requires=firefly-gaf.service

[Timer]
OnCalendar=*-*-* 23:05:00
Unit=firefly-gaf.service

[Install]
WantedBy=timers.target
```

3. Reload systemd and enable the timer

```console
$ systemctl --user daemon-reload
$ systemctl --user enable --now firefly-gaf.timer
```

## Options

All options can be provided via cli or environment variables, when both are used, the value provided via cli takes precedence.

| Option | Env var | Description |
| --- | --- | --- |
| `-l/--log-level` | `LOG_LEVEL` | The log level of the script. |
| `-u/--url` | `FIREFLY_III_URL` | The url of the firefly instance where the transactions are available. |
| `-t/--access-token` | `FIREFLY_III_ACCESS_TOKEN` | The firefly user personal access token required to access and modify the user transactions and rules. |
| `-g/--group` | `FIREFLY_III_RULE_GROUP` | The name of the group in which the rules should be created. |
| `--dry-run` | `DRY_RUN` | Whether the script should be executed in read-only mode, only searching for rules to create. |
| `<argument>` | `ACCOUNT_NAME` | The name of the "generic" account, in which the mislabelled transactions can be found. |
