"""Dependency-free string transforms and a macOS clipboard command line interface."""

import argparse
import json
import subprocess
import sys
import unicodedata


COMMANDS = (
    "json.pretty",
    "camelCase",
    "snake_case",
    "underscore_case",
    "kebab-case",
    "lowercase",
    "uppercase",
)
_LINE_ENDINGS = "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"


def _reject_constant(value: str) -> None:
    raise ValueError("JSON numbers must be finite.")


def _words(line: str) -> list[str]:
    words = []
    word = []
    previous = ""
    for index, character in enumerate(line):
        if unicodedata.category(character).startswith("M"):
            if word:
                word.append(character)
            continue
        if not character.isalnum():
            if word:
                words.append("".join(word))
                word = []
            previous = ""
            continue
        following = line[index + 1] if index + 1 < len(line) else ""
        if word and character.isupper() and (
            previous.islower()
            or previous.isdigit()
            or (previous.isupper() and following.islower())
        ):
            words.append("".join(word))
            word = []
        word.append(character)
        previous = character
    if word:
        words.append("".join(word))
    return words


def transform(operation: str, text: str) -> str:
    """Transform text without I/O; raise ValueError for an unsupported command or JSON."""
    if operation not in COMMANDS:
        raise ValueError("Unsupported string operation.")
    if operation == "json.pretty":
        try:
            value = json.loads(text, parse_constant=_reject_constant)
            return json.dumps(value, indent=4, sort_keys=True, ensure_ascii=False, allow_nan=False)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid JSON at line {error.lineno}, column {error.colno}."
            ) from None
        except ValueError:
            raise ValueError("Invalid JSON: numbers must be finite and within supported limits.") from None
        except RecursionError:
            raise ValueError("Invalid JSON: nesting is too deep.") from None
    if operation == "lowercase":
        return text.lower()
    if operation == "uppercase":
        return text.upper()

    converted = []
    for line in text.splitlines(keepends=True):
        body = line.rstrip(_LINE_ENDINGS)
        ending = line[len(body):]
        words = [word.lower() for word in _words(body)]
        if operation == "camelCase":
            result = words[0] if words else ""
            result += "".join(word[0].upper() + word[1:] for word in words[1:])
        else:
            separator = "-" if operation == "kebab-case" else "_"
            result = separator.join(words)
        converted.append(result + ending)
    return "".join(converted)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Transform clipboard text with String Operations.")
    parser.add_argument("operation", choices=COMMANDS)
    parser.add_argument(
        "--stdin", action="store_true", help="Read UTF-8 stdin and write stdout without using the clipboard."
    )
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code)

    action = "read standard input" if arguments.stdin else "read the clipboard"
    try:
        if arguments.stdin:
            source = sys.stdin.buffer.read().decode("utf-8")
        else:
            source = subprocess.run(
                ["/usr/bin/pbpaste"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            ).stdout.decode("utf-8")
        action = "transform the text"
        result = transform(arguments.operation, source)
        action = "encode the result"
        output = result.encode("utf-8")
        action = "write standard output" if arguments.stdin else "write the clipboard"
        if arguments.stdin:
            sys.stdout.buffer.write(output)
            sys.stdout.buffer.flush()
        else:
            subprocess.run(
                ["/usr/bin/pbcopy"], input=output, check=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
        return 0
    except UnicodeError:
        message = f"Could not {action}: text must be valid UTF-8."
    except subprocess.CalledProcessError as error:
        message = f"Could not {action} (exit status {error.returncode})."
    except OSError:
        message = f"Could not {action}: operating system error."
    except ValueError as error:
        message = str(error)
    print(f"String Operations: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
