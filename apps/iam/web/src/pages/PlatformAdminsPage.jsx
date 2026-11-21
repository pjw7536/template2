import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { findUser, groupByPath, groupMembers, joinGroupById } from "@/lib/api"
import { displayName } from "@/lib/users"

export default function PlatformAdminsPage() {
  const [groupId, setGroupId] = useState("")
  const [members, setMembers] = useState([])
  const [epid, setEpid] = useState("")
  const [candidate, setCandidate] = useState(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const group = await groupByPath("/iam/platform-admins")
        const users = await groupMembers(group.id)
        if (!active) return
        setMembers(users)
        setGroupId(group.id)
      } catch (failure) {
        if (active) setError(failure.message)
      }
    }
    load()
    return () => { active = false }
  }, [])

  async function lookup(event) {
    event.preventDefault()
    if (!epid.trim() || pending) return
    setCandidate(null)
    setNotice("")
    setError("")
    setPending(true)
    try {
      const user = await findUser(epid.trim())
      if (!user) throw new Error("이 EPID의 계정을 찾지 못했습니다. EPID와 사내 SSO 첫 로그인 여부를 확인하세요.")
      if (user.enabled === false) throw new Error("비활성화된 계정입니다.")
      if (members.some((member) => member.id === user.id)) throw new Error("이미 등록된 플랫폼 관리자입니다.")
      setCandidate(user)
    } catch (failure) {
      setError(failure.message)
    } finally {
      setPending(false)
    }
  }

  async function grant() {
    if (!candidate || pending) return
    setError("")
    setPending(true)
    try {
      await joinGroupById(candidate.id, groupId)
      setMembers((current) => [...current, candidate])
      setNotice(`${displayName(candidate)} 계정에 권한을 부여했습니다. 다음 로그인부터 사용할 수 있습니다.`)
      setCandidate(null)
      setEpid("")
    } catch (failure) {
      setError(failure.message)
    } finally {
      setPending(false)
    }
  }

  return (
    <section className="grid max-w-2xl gap-4" aria-labelledby="platform-admins-heading">
      <h2 id="platform-admins-heading" className="text-xl font-semibold">플랫폼 관리자</h2>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {notice && <p role="status" className="text-sm">{notice}</p>}
      {!groupId && !error && <p role="status" className="text-sm text-muted-foreground">관리자 목록을 불러오는 중…</p>}
      {groupId && (
        <>
          <form className="flex items-end gap-2" onSubmit={lookup}>
            <div className="grid gap-2">
              <Label htmlFor="admin-epid">추가할 계정의 EPID</Label>
              <Input id="admin-epid" value={epid} disabled={pending} onChange={(event) => {
                setEpid(event.target.value)
                setCandidate(null)
                setNotice("")
                setError("")
              }} />
            </div>
            <Button type="submit" variant="outline" disabled={!epid.trim() || pending}>계정 확인</Button>
          </form>
          {candidate && (
            <div className="flex items-center gap-3 rounded-md border p-3 text-sm">
              <span>{displayName(candidate)}</span>
              <span className="text-muted-foreground">{candidate.username}</span>
              <Button className="ml-auto" disabled={pending} onClick={grant}>권한 부여</Button>
            </div>
          )}
          <div className="rounded-md border">
            <Table aria-label="등록된 플랫폼 관리자">
              <TableHeader>
                <TableRow><TableHead>사용자</TableHead><TableHead>EPID</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {members.map((member) => (
                  <TableRow key={member.id}>
                    <TableCell>{displayName(member)}</TableCell>
                    <TableCell className="text-muted-foreground">{member.username}</TableCell>
                  </TableRow>
                ))}
                {members.length === 0 && <TableRow><TableCell colSpan={2}>등록된 플랫폼 관리자가 없습니다.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </section>
  )
}
