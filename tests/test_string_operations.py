import contextlib
import io
import subprocess
import sys
import unittest
from unittest import mock

from workflow import string_operations


class TransformTests(unittest.TestCase):
    def test_commands_contain_only_the_seven_requested_names(self):
        self.assertEqual(
            (
                "json.pretty", "camelCase", "snake_case", "underscore_case",
                "kebab-case", "lowercase", "uppercase",
            ),
            string_operations.COMMANDS,
        )

    def test_unknown_operation_raises_a_readable_error(self):
        with self.assertRaisesRegex(ValueError, "Unsupported string operation"):
            string_operations.transform("titlecase", "private text")

    def test_json_pretty_sorts_nested_keys_and_uses_four_spaces_and_unicode(self):
        source = '{"z":[3,{"b":true,"a":null}],"a":"café 你好"}'
        expected = (
            '{\n'
            '    "a": "café 你好",\n'
            '    "z": [\n'
            '        3,\n'
            '        {\n'
            '            "a": null,\n'
            '            "b": true\n'
            '        }\n'
            '    ]\n'
            '}'
        )
        self.assertEqual(expected, string_operations.transform("json.pretty", source))

    def test_json_pretty_accepts_top_level_arrays_and_scalars(self):
        for source, expected in (
            ("[2,1]", "[\n    2,\n    1\n]"),
            ('"hello"', '"hello"'),
            ("42", "42"),
            ("1.25", "1.25"),
            ("true", "true"),
            ("false", "false"),
            ("null", "null"),
        ):
            with self.subTest(source=source):
                self.assertEqual(expected, string_operations.transform("json.pretty", source))

    def test_invalid_json_reports_a_location_without_the_source_text(self):
        with self.assertRaises(ValueError) as raised:
            string_operations.transform("json.pretty", '{\n"private-token": }')
        self.assertEqual("Invalid JSON at line 2, column 18.", str(raised.exception))
        self.assertNotIn("private-token", str(raised.exception))

    def test_empty_or_malformed_json_is_rejected(self):
        for source in ("", " ", "{", "[1,]", '{"a":1} extra', "{'a': 1}"):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "Invalid JSON"):
                string_operations.transform("json.pretty", source)

    def test_nonfinite_and_overflowing_json_numbers_are_rejected(self):
        for source in ("NaN", "Infinity", "-Infinity", "1e999", "-1e999", '{"a":[NaN]}'):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "numbers must be finite"):
                string_operations.transform("json.pretty", source)

    def test_excessive_json_nesting_is_rejected_without_a_traceback(self):
        source = "[" * 10000 + "0" + "]" * 10000
        with self.assertRaisesRegex(ValueError, "nesting is too deep"):
            string_operations.transform("json.pretty", source)

    def test_identifier_operations_split_camel_pascal_and_acronym_boundaries(self):
        for source, camel, snake, kebab in (
            ("helloWorld", "helloWorld", "hello_world", "hello-world"),
            ("HelloWorld", "helloWorld", "hello_world", "hello-world"),
            ("HTTPResponseCode", "httpResponseCode", "http_response_code", "http-response-code"),
            ("parseXMLDocument", "parseXmlDocument", "parse_xml_document", "parse-xml-document"),
            ("XMLHttpRequest", "xmlHttpRequest", "xml_http_request", "xml-http-request"),
            ("API", "api", "api", "api"),
        ):
            for operation, expected in (
                ("camelCase", camel), ("snake_case", snake),
                ("underscore_case", snake), ("kebab-case", kebab),
            ):
                with self.subTest(source=source, operation=operation):
                    self.assertEqual(expected, string_operations.transform(operation, source))

    def test_identifier_operations_keep_digits_attached_to_words(self):
        for source, expected in (
            ("HTTP2Server", "http2_server"),
            ("version42Value", "version42_value"),
            ("a1b2", "a1b2"),
            ("123go", "123go"),
            ("UTF8Decoder", "utf8_decoder"),
        ):
            with self.subTest(source=source):
                self.assertEqual(expected, string_operations.transform("snake_case", source))

    def test_identifier_operations_collapse_and_trim_punctuation_and_whitespace(self):
        source = "  Hello...WORLD__again /and\tfriends! 👋 "
        for operation, expected in (
            ("camelCase", "helloWorldAgainAndFriends"),
            ("snake_case", "hello_world_again_and_friends"),
            ("underscore_case", "hello_world_again_and_friends"),
            ("kebab-case", "hello-world-again-and-friends"),
        ):
            with self.subTest(operation=operation):
                self.assertEqual(expected, string_operations.transform(operation, source))

    def test_identifier_operations_keep_unicode_letters_and_combining_marks(self):
        self.assertEqual(
            "déjà_vu_éclair_http_value_cafe\u0301_name_你好",
            string_operations.transform("snake_case", "déjàVu ÉclairHTTPValue Cafe\u0301Name 你好"),
        )

    def test_identifier_operations_convert_lines_independently_and_preserve_line_endings(self):
        source = " FirstValue \r\nXMLHttpRequest\r\n\rThird LINE\nLastWord"
        for operation, expected in (
            ("camelCase", "firstValue\r\nxmlHttpRequest\r\n\rthirdLine\nlastWord"),
            ("snake_case", "first_value\r\nxml_http_request\r\n\rthird_line\nlast_word"),
            ("underscore_case", "first_value\r\nxml_http_request\r\n\rthird_line\nlast_word"),
            ("kebab-case", "first-value\r\nxml-http-request\r\n\rthird-line\nlast-word"),
        ):
            with self.subTest(operation=operation):
                self.assertEqual(expected, string_operations.transform(operation, source))

    def test_identifier_operations_preserve_all_python_line_separators(self):
        for ending in ("\n", "\r", "\r\n", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"):
            with self.subTest(ending=repr(ending)):
                self.assertEqual(
                    "first_word" + ending + "second_word" + ending,
                    string_operations.transform("snake_case", "First Word" + ending + "Second Word" + ending),
                )

    def test_identifier_operations_turn_separator_only_lines_into_empty_lines(self):
        for operation in ("camelCase", "snake_case", "underscore_case", "kebab-case"):
            with self.subTest(operation=operation):
                self.assertEqual("\r\n\n", string_operations.transform(operation, " -_ \r\n\t!\n"))
                self.assertEqual("", string_operations.transform(operation, "\u0301"))

    def test_empty_text_stays_empty_for_all_case_operations(self):
        for operation in string_operations.COMMANDS[1:]:
            with self.subTest(operation=operation):
                self.assertEqual("", string_operations.transform(operation, ""))

    def test_lowercase_uses_unicode_case_conversion_without_changing_whitespace(self):
        self.assertEqual(
            "  straße i\u0307stanbul ος\tå\r\n你好 123\n",
            string_operations.transform("lowercase", "  Straße İSTANBUL ΟΣ\tÅ\r\n你好 123\n"),
        )

    def test_uppercase_uses_unicode_case_conversion_without_changing_whitespace(self):
        self.assertEqual(
            "  STRASSE CAFÉ\tÅ\r\n你好 123\n",
            string_operations.transform("uppercase", "  Straße café\tå\r\n你好 123\n"),
        )


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.clipboard_process = mock.Mock(side_effect=AssertionError("Unexpected clipboard access"))

    def invoke(self, arguments, source=b""):
        standard_input = io.TextIOWrapper(io.BytesIO(source), encoding="utf-8", newline="")
        output_buffer = io.BytesIO()
        standard_output = io.TextIOWrapper(output_buffer, encoding="utf-8", newline="")
        errors = io.StringIO()
        with (
            mock.patch.object(string_operations.subprocess, "run", self.clipboard_process),
            mock.patch.object(sys, "stdin", standard_input),
            contextlib.redirect_stdout(standard_output),
            contextlib.redirect_stderr(errors),
        ):
            status = string_operations.main(arguments)
        standard_output.flush()
        return status, output_buffer.getvalue(), errors.getvalue()

    def test_clipboard_success_copies_only_the_transformed_utf8_bytes(self):
        self.clipboard_process.side_effect = [
            subprocess.CompletedProcess(["/usr/bin/pbpaste"], 0, "CaféName\r\n".encode()),
            subprocess.CompletedProcess(["/usr/bin/pbcopy"], 0),
        ]
        self.assertEqual((0, b"", ""), self.invoke(["snake_case"]))
        self.assertEqual(
            [
                mock.call(["/usr/bin/pbpaste"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE),
                mock.call(
                    ["/usr/bin/pbcopy"], input="café_name\r\n".encode(), check=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                ),
            ],
            self.clipboard_process.call_args_list,
        )

    def test_invalid_json_never_starts_pbcopy_or_exposes_clipboard_text(self):
        for source in (b'{"private-token": }', b'{"private-token": NaN}', b'{"private-token": 1e999}'):
            with self.subTest(source=source):
                self.clipboard_process.reset_mock()
                self.clipboard_process.side_effect = [subprocess.CompletedProcess(["/usr/bin/pbpaste"], 0, source)]
                status, output, errors = self.invoke(["json.pretty"])
                self.assertEqual(1, status)
                self.assertEqual(b"", output)
                self.assertIn("Invalid JSON", errors)
                self.assertNotIn("private-token", errors)
                self.clipboard_process.assert_called_once_with(
                    ["/usr/bin/pbpaste"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )

    def test_non_utf8_clipboard_data_fails_before_pbcopy_without_exposing_text(self):
        self.clipboard_process.side_effect = [
            subprocess.CompletedProcess(["/usr/bin/pbpaste"], 0, b"private-token\xff")
        ]
        status, output, errors = self.invoke(["lowercase"])
        self.assertEqual(1, status)
        self.assertEqual(b"", output)
        self.assertIn("read the clipboard: text must be valid UTF-8", errors)
        self.assertNotIn("private-token", errors)
        self.assertEqual(1, self.clipboard_process.call_count)

    def test_json_with_a_lone_surrogate_fails_before_pbcopy(self):
        self.clipboard_process.side_effect = [
            subprocess.CompletedProcess(["/usr/bin/pbpaste"], 0, b'{"private-token":"\\ud800"}')
        ]
        status, output, errors = self.invoke(["json.pretty"])
        self.assertEqual(1, status)
        self.assertEqual(b"", output)
        self.assertIn("encode the result: text must be valid UTF-8", errors)
        self.assertNotIn("private-token", errors)
        self.assertEqual(1, self.clipboard_process.call_count)

    def test_pbpaste_process_failure_reports_status_without_copying_or_leaking_output(self):
        self.clipboard_process.side_effect = subprocess.CalledProcessError(
            3, ["/usr/bin/pbpaste"], output=b"private-output", stderr=b"private-error"
        )
        status, output, errors = self.invoke(["uppercase"])
        self.assertEqual(1, status)
        self.assertEqual(b"", output)
        self.assertIn("read the clipboard (exit status 3)", errors)
        self.assertNotIn("private", errors)
        self.assertEqual(1, self.clipboard_process.call_count)

    def test_missing_clipboard_tool_returns_a_readable_error(self):
        self.clipboard_process.side_effect = FileNotFoundError("private-error")
        status, output, errors = self.invoke(["uppercase"])
        self.assertEqual(1, status)
        self.assertEqual(b"", output)
        self.assertIn("read the clipboard: operating system error", errors)
        self.assertNotIn("private-error", errors)
        self.assertEqual(1, self.clipboard_process.call_count)

    def test_pbcopy_process_failure_returns_nonzero_without_leaking_output(self):
        self.clipboard_process.side_effect = [
            subprocess.CompletedProcess(["/usr/bin/pbpaste"], 0, b"private-input"),
            subprocess.CalledProcessError(5, ["/usr/bin/pbcopy"], stderr=b"private-error"),
        ]
        status, output, errors = self.invoke(["uppercase"])
        self.assertEqual(1, status)
        self.assertEqual(b"", output)
        self.assertIn("write the clipboard (exit status 5)", errors)
        self.assertNotIn("private", errors)
        self.assertEqual(b"PRIVATE-INPUT", self.clipboard_process.call_args.kwargs["input"])

    def test_pbcopy_os_failure_returns_nonzero_without_leaking_input(self):
        self.clipboard_process.side_effect = [
            subprocess.CompletedProcess(["/usr/bin/pbpaste"], 0, b"private-input"),
            OSError("private-error"),
        ]
        status, output, errors = self.invoke(["uppercase"])
        self.assertEqual(1, status)
        self.assertEqual(b"", output)
        self.assertIn("write the clipboard: operating system error", errors)
        self.assertNotIn("private", errors)

    def test_stdin_mode_runs_every_operation_without_clipboard_access(self):
        for operation, source, expected in (
            ("json.pretty", b'{"z":2,"a":1}', b'{\n    "a": 1,\n    "z": 2\n}'),
            ("camelCase", b"Hello World", b"helloWorld"),
            ("snake_case", b"Hello World", b"hello_world"),
            ("underscore_case", b"Hello World", b"hello_world"),
            ("kebab-case", b"Hello World", b"hello-world"),
            ("lowercase", "CAFÉ".encode(), "café".encode()),
            ("uppercase", "Straße".encode(), b"STRASSE"),
        ):
            with self.subTest(operation=operation):
                self.assertEqual((0, expected, ""), self.invoke([operation, "--stdin"], source))
        self.clipboard_process.assert_not_called()

    def test_stdin_mode_preserves_crlf_and_adds_no_trailing_newline(self):
        self.assertEqual(
            (0, b"first_word\r\nsecond_word", ""),
            self.invoke(["--stdin", "snake_case"], b"First Word\r\nSecond Word"),
        )
        self.clipboard_process.assert_not_called()

    def test_stdin_invalid_json_writes_no_stdout_and_does_not_access_clipboard(self):
        status, output, errors = self.invoke(["json.pretty", "--stdin"], b'{"private-token":}')
        self.assertEqual(1, status)
        self.assertEqual(b"", output)
        self.assertIn("Invalid JSON", errors)
        self.assertNotIn("private-token", errors)
        self.clipboard_process.assert_not_called()

    def test_stdin_invalid_utf8_returns_a_readable_error_without_leaking_input(self):
        status, output, errors = self.invoke(["lowercase", "--stdin"], b"private-token\xff")
        self.assertEqual(1, status)
        self.assertEqual(b"", output)
        self.assertIn("read standard input: text must be valid UTF-8", errors)
        self.assertNotIn("private-token", errors)
        self.clipboard_process.assert_not_called()

    def test_missing_unknown_and_extra_arguments_fail_before_clipboard_access(self):
        for arguments in ([], ["titlecase"], ["lowercase", "extra"], ["lowercase", "--unknown"]):
            with self.subTest(arguments=arguments):
                status, output, errors = self.invoke(arguments)
                self.assertEqual(2, status)
                self.assertEqual(b"", output)
                self.assertIn("usage:", errors)
        self.clipboard_process.assert_not_called()

    def test_help_lists_all_commands_without_clipboard_access(self):
        status, output, errors = self.invoke(["--help"])
        self.assertEqual(0, status)
        self.assertEqual("", errors)
        for operation in string_operations.COMMANDS:
            self.assertIn(operation, output.decode())
        self.assertIn("--stdin", output.decode())
        self.clipboard_process.assert_not_called()

    def test_main_without_arguments_uses_the_process_arguments(self):
        with mock.patch.object(sys, "argv", ["string_operations.py", "--stdin", "uppercase"]):
            self.assertEqual((0, b"HELLO", ""), self.invoke(None, b"hello"))
        self.clipboard_process.assert_not_called()


if __name__ == "__main__":
    unittest.main()
