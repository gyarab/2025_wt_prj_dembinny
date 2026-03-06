"""
importer/tests.py
─────────────────
Unit tests for the pure CSV parser (importer.parser).
No database required — these run with plain Python.
"""

from django.test import SimpleTestCase

from .parser import parse_csv_text, IMPORTABLE_ROLES


class ParserStructureTests(SimpleTestCase):
    """Tests for structural (header-level) validation."""

    def test_missing_header_returns_field_error(self):
        result = parse_csv_text('')
        self.assertTrue(result.field_errors)

    def test_empty_data_rows(self):
        csv = 'first_name,last_name\n'
        result = parse_csv_text(csv)
        # No structural errors — just zero data rows
        self.assertFalse(result.field_errors)
        self.assertEqual(len(result.rows), 0)

    def test_minimal_valid_csv_first_last(self):
        csv = 'first_name,last_name\nJan,Novák\n'
        result = parse_csv_text(csv)
        self.assertFalse(result.field_errors)
        self.assertEqual(len(result.rows), 1)
        self.assertTrue(result.rows[0].is_valid)

    def test_minimal_valid_csv_username_only(self):
        csv = 'username\njnovak\n'
        result = parse_csv_text(csv)
        self.assertFalse(result.field_errors)
        self.assertTrue(result.rows[0].is_valid)
        self.assertEqual(result.rows[0].username, 'jnovak')

    def test_minimal_valid_csv_email_only(self):
        csv = 'email\njan@example.com\n'
        result = parse_csv_text(csv)
        self.assertFalse(result.field_errors)
        self.assertTrue(result.rows[0].is_valid)
        # local-part used as username candidate
        self.assertEqual(result.rows[0].username, 'jan')

    def test_column_names_are_case_insensitive(self):
        csv = 'First_Name,Last_Name\nJan,Novák\n'
        result = parse_csv_text(csv)
        self.assertFalse(result.field_errors)
        self.assertEqual(result.rows[0].first_name, 'Jan')


class ParserRowTests(SimpleTestCase):
    """Tests for per-row validation."""

    def _parse(self, body: str):
        return parse_csv_text(f'first_name,last_name,parent_email,variable_symbol\n{body}')

    def test_no_identity_produces_error(self):
        # Empty first_name, last_name, no username or email column → identity error
        result = self._parse(',,,')
        self.assertFalse(result.rows[0].is_valid)
        self.assertTrue(any('identifier' in e for e in result.rows[0].errors))

    def test_only_first_name_is_invalid(self):
        result = self._parse('Jan,,,')
        self.assertFalse(result.rows[0].is_valid)

    def test_only_last_name_is_invalid(self):
        result = self._parse(',Novák,,')
        self.assertFalse(result.rows[0].is_valid)

    def test_invalid_parent_email(self):
        result = self._parse('Jan,Novák,notanemail,')
        self.assertFalse(result.rows[0].is_valid)

    def test_non_numeric_vs(self):
        result = self._parse('Jan,Novák,,ABC')
        self.assertFalse(result.rows[0].is_valid)

    def test_vs_too_long(self):
        result = self._parse('Jan,Novák,,12345678901')
        self.assertFalse(result.rows[0].is_valid)

    def test_duplicate_vs_within_file(self):
        csv = 'first_name,last_name,variable_symbol\nJan,Novák,001\nPetr,Svoboda,001\n'
        result = parse_csv_text(csv)
        # Second row should have the duplicate error
        self.assertFalse(result.rows[1].is_valid)

    def test_valid_row_with_parent(self):
        result = self._parse('Jan,Novák,jan.parent@example.com,04001')
        row = result.rows[0]
        self.assertTrue(row.is_valid)
        self.assertTrue(row.has_parent)
        self.assertEqual(row.variable_symbol, '04001')

    def test_username_derived_from_name(self):
        csv = 'first_name,last_name\nJan,Novak\n'
        result = parse_csv_text(csv)
        self.assertEqual(result.rows[0].username, 'jnovak')

    def test_explicit_username_preserved(self):
        csv = 'first_name,last_name,username\nJan,Novak,jnovak2\n'
        result = parse_csv_text(csv)
        self.assertEqual(result.rows[0].username, 'jnovak2')

    def test_valid_and_invalid_rows_mixed(self):
        csv = 'first_name,last_name\nJan,Novák\n,Svoboda\nPetr,Dvořák\n'
        result = parse_csv_text(csv)
        self.assertEqual(len(result.valid_rows), 2)
        self.assertEqual(len(result.error_rows), 1)

    def test_extra_roles_accepted(self):
        csv = 'username,role\njnovak,Auditor\n'
        result = parse_csv_text(csv, extra_roles={'Auditor'})
        self.assertTrue(result.rows[0].is_valid)

    def test_unknown_role_rejected(self):
        csv = 'username,role\njnovak,Auditor\n'
        result = parse_csv_text(csv)
        self.assertFalse(result.rows[0].is_valid)


class ParserBytesTests(SimpleTestCase):
    """Test the bytes → text wrapper."""

    def test_utf8_bom_decoded(self):
        from .parser import parse_csv_bytes
        raw = 'first_name,last_name\nJan,Novák\n'.encode('utf-8-sig')
        result = parse_csv_bytes(raw)
        self.assertFalse(result.field_errors)
        self.assertEqual(result.rows[0].first_name, 'Jan')

    def test_bad_encoding_raises_value_error(self):
        from .parser import parse_csv_bytes
        with self.assertRaises(ValueError):
            parse_csv_bytes(b'\xff\xfe bad bytes')
