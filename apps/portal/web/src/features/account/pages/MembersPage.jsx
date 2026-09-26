import { useQuery } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth"
import { accountApi } from "../api/accountApi"

export default function MembersPage() {
  const { user } = useAuth()
  const query = useQuery({ queryKey: ["account", "keycloak-members"], queryFn: () => accountApi.fetchUserPool({ limit: 500 }), enabled: Boolean(user?.isPortalAdmin) })
  if (!user?.isPortalAdmin) return <p className="p-6 text-sm text-muted-foreground">전체 관리자만 사용자 목록을 조회할 수 있습니다.</p>
  return (
    <div className="flex h-full min-h-0 flex-col gap-4 px-6 py-4">
      <h2 className="text-2xl font-semibold tracking-tight">Portal 사용자</h2>
      <p className="text-sm text-muted-foreground">Portal에 로그인한 사용자의 마지막 로그인 정보를 표시합니다. 소속과 권한은 Keycloak에서 변경하세요. 최대 500명을 표시합니다.</p>
      {query.isPending ? <p role="status">불러오는 중…</p> : query.isError ? <div role="alert"><p className="text-sm text-destructive">사용자 정보를 불러오지 못했습니다.</p><Button onClick={() => query.refetch()} variant="outline">다시 시도</Button></div> : (
        <div className="min-h-0 overflow-auto rounded-lg border bg-card">
          <table className="w-full text-left text-sm"><thead className="sticky top-0 border-b bg-muted"><tr>{["이름", "Knox ID", "부서", "소속 SDWT"].map((label) => <th key={label} className="px-4 py-3 font-medium">{label}</th>)}</tr></thead><tbody>
            {(query.data?.results || []).map((member) => <tr key={member.id} className="border-b hover:bg-muted/50">{[member.username, member.knoxId, member.department, member.userSdwtProd].map((value, index) => <td key={index} className="px-4 py-3">{value || "미지정"}</td>)}</tr>)}
            {!query.data?.results?.length ? <tr><td colSpan={4} className="px-4 py-6 text-muted-foreground">로그인한 사용자가 없습니다.</td></tr> : null}
          </tbody></table>
        </div>
      )}
    </div>
  )
}
