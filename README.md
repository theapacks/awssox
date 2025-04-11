# awssox

An interactive CLI tool to simplify **AWS SSO** logins and optional role assumptions.

## Table of Contents

-   [Features](#features)
-   [Installation](#installation)
-   [Usage](#usage)
    -   [Listing Profiles](#listing-profiles)
    -   [Logging In](#logging-in)
    -   [Role Assumption](#role-assumption)
-   [Development](#development)
-   [License](#license)

---

## Features

-   **List AWS Profiles**: Quickly see all profiles from your `~/.aws/config`.
-   **SSO Login Flow**: Log in to AWS SSO without manually typing profiles.
-   **Role Assumption**: If your chosen profile has an associated roles profile, you can select and assume it.

---

## Installation

---

## Usage

```bash
$ pip install awssox
```

### Listing Profiles

```bash
$ awssox list-profiles
```

### Logging In

```bash
$ awssox login
```

---

## Development

---

## License

This project is licensed under the MIT License

---
