Browser automation — navigate pages, take screenshots, extract content, run JavaScript.

## Usage

### Open a URL and get page info + screenshot
```
claw browse open https://example.com
claw browse open https://example.com --headed --profile mysite
```

### Take a screenshot
```
claw browse screenshot https://example.com
claw browse screenshot https://example.com --selector "#main" --output page.png
```

### Extract text content
```
claw browse extract https://example.com
claw browse extract https://example.com --selector "h1"
```

### Extract a table
```
claw browse table https://example.com/data
claw browse table https://example.com --selector "#results"
```

### Evaluate JavaScript
```
claw browse js https://example.com "document.title"
claw browse js https://example.com "document.querySelectorAll('a').length"
```

### Manage browser profiles
```
claw browse profiles
claw browse profiles delete myprofile
```

## Options

- `--profile NAME` — Use a named browser profile (persistent cookies/localStorage)
- `--headed` — Run in visible browser mode (default is headless)

## Configuration

- Profiles stored at: `~/.claude-superpowers/browser/profiles/`
- Screenshots default to temp files unless `--output` is specified

```
cd ~/Projects/claude-superpowers && claw browse $ARGUMENTS
```
