"""Airflow SSO 기본 조회·승격·신원 분리 계약을 검증한다."""

import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('oidc_claims', Path(__file__).resolve().parents[1] / 'image/oidc_claims.py')
claims_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(claims_module)


class OidcClaimsTests(unittest.TestCase):
    def info(self, **claims):
        return claims_module.user_info({'iss': 'https://sso.test/realms/main', 'sub': 'subject-1', **claims},
                                      'https://sso.test/realms/main', 'airflow')

    def test_default_viewer_and_foreign_roles(self):
        self.assertEqual(self.info()['role_keys'], ['Viewer'])
        self.assertEqual(self.info(resource_access={'portal': {'roles': ['Admin']}},
                                   groups=['/SDWT-A/admin'])['role_keys'], ['Viewer'])
        self.assertEqual(self.info(resource_access={'airflow': {'roles': ['unknown']}})['role_keys'], ['Viewer'])

    def test_native_roles_and_removal(self):
        self.assertEqual(self.info(resource_access={'airflow': {'roles': ['Admin', 'User']}})['role_keys'],
                         ['Admin', 'User', 'Viewer'])
        self.assertEqual(self.info(resource_access={'airflow': {'roles': []}})['role_keys'], ['Viewer'])

    def test_malformed_claims_do_not_become_viewer(self):
        for value in (None, [], {'airflow': None}, {'airflow': {'roles': 'Admin'}}, {'airflow': {'roles': [1]}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.info(resource_access=value)
        for values in ({'sub': ''}, {'sub': 1}, {'iss': 'https://other.test'}, {'email': []}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.info(**values)

    def test_username_is_subject_based_and_not_email(self):
        first = self.info(email='same@example.test')
        second = self.info(sub='subject-2', email='same@example.test')
        renamed = self.info(email='new@example.test', preferred_username='airflow')
        self.assertNotEqual(first['username'], second['username'])
        self.assertEqual(first['username'], renamed['username'])
        self.assertTrue(first['username'].startswith('kc_'))
        self.assertLessEqual(len(first['username']), 256)
