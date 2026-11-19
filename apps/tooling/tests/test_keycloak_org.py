"""소속별 역할(client org) 계산과 토큰 scope 정의를 서버 없이 검사합니다."""

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2].parent
SCRIPTS = ROOT / "deploy/keycloak/scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("org_sync", SCRIPTS / "org_sync.py")
org = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(org)

TREE = [
    {"name": "TEAM-1", "lines": [
        {"name": "LINE-1", "sdwts": ["SDWT-C", "SDWT-D"]},
        {"name": "LINE-2", "sdwts": ["SDWT-E"]},
    ]},
    {"name": "TEAM-2", "lines": [{"name": "LINE-1", "sdwts": ["SDWT-F"]}]},
]


class RoleTests(unittest.TestCase):
    def test_sdwt_roles_are_plain_and_line_team_roles_expand_to_sdwts(self):
        roles = org.desired_roles(TREE)
        self.assertIsNone(roles["sdwt:SDWT-C:admin"]["composites"])
        self.assertEqual(roles["team:TEAM-1:line:LINE-1:admin"]["composites"], ["sdwt:SDWT-C:admin", "sdwt:SDWT-D:admin"])
        self.assertEqual(roles["team:TEAM-1:viewer"]["composites"], ["sdwt:SDWT-C:viewer", "sdwt:SDWT-D:viewer", "sdwt:SDWT-E:viewer"])
        # 같은 라인 이름이 다른 팀에 있어도 라인 역할은 팀으로 구분됩니다.
        self.assertEqual(roles["team:TEAM-2:line:LINE-1:user"]["composites"], ["sdwt:SDWT-F:user"])
        self.assertEqual(len(roles), 4 * 3 + 3 * 3 + 2 * 3)

    def test_token_scope_allows_only_sdwt_roles(self):
        allowed = org.token_roles(org.desired_roles(TREE))
        self.assertEqual(len(allowed), 4 * 3)
        self.assertTrue(all(name.startswith("sdwt:") for name in allowed))

    def test_claims_scope_issues_affiliation_object_and_org_roles_list(self):
        scope = org.claims_scope()
        claims = {mapper["config"]["claim.name"]: mapper for mapper in scope["protocolMappers"]}
        self.assertEqual(claims["affiliation.team"]["config"]["user.attribute"], "deptname")
        self.assertEqual(claims["affiliation.line"]["config"]["user.attribute"], "line_id")
        self.assertEqual(claims["affiliation.sdwt"]["config"]["user.attribute"], "user_sdwt_prod")
        self.assertEqual(claims["org_roles"]["config"]["usermodel.clientRoleMapping.clientId"], "org")
        self.assertEqual(claims["org_roles"]["config"]["multivalued"], "true")


if __name__ == "__main__":
    unittest.main()
