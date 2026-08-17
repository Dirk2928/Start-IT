import { useEffect, useMemo, useState } from 'react'

const NO_GROUP = 'No Group'
const ALL_GROUPS = 'All Groups'

const emptyForm = {
  id: null,
  name: '',
  url: '',
  icon: '',
  groupId: null,
  browser: 'System Default',
}

function App() {
  const [groups, setGroups] = useState([])
  const [links, setLinks] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [selectedIds, setSelectedIds] = useState([])
  const [filterGroupId, setFilterGroupId] = useState(null)
  const [newGroupName, setNewGroupName] = useState('')
  const [status, setStatus] = useState('')
  const [browserInfo, setBrowserInfo] = useState({ options: ['System Default'], detected: {} })

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds])

  const loadGroups = async () => {
    const rows = await window.api.listGroups()
    setGroups(rows)
    return rows
  }

  const loadLinks = async (groupId = filterGroupId) => {
    const rows = await window.api.listLinks(groupId)
    setLinks(rows)
    setSelectedIds([])
  }

  useEffect(() => {
    const setup = async () => {
      const browsers = await window.api.getBrowsers()
      setBrowserInfo(browsers)
      await loadGroups()
      await loadLinks(null)
    }
    setup()
  }, [])

  const onSave = async () => {
    const result = await window.api.saveLink(form)
    if (!result.ok) {
      setStatus(result.message)
      return
    }
    setForm(emptyForm)
    setStatus('Link saved.')
    await loadLinks()
  }

  const onDelete = async () => {
    if (!selectedIds.length) {
      setStatus('Select at least one link to delete.')
      return
    }
    await window.api.deleteLinks(selectedIds)
    setStatus('Selected link(s) deleted.')
    await loadLinks()
  }

  const onLaunchSelected = async () => {
    if (!selectedIds.length) {
      setStatus('Select at least one link to launch.')
      return
    }
    const result = await window.api.launchSelected(selectedIds)
    setStatus(result.errors?.length ? result.errors.slice(0, 6).join('\n') : 'Selected links launched.')
  }

  const onLaunchVisible = async () => {
    const result = await window.api.launchVisible(filterGroupId)
    setStatus(result.errors?.length ? result.errors.slice(0, 6).join('\n') : 'Visible links launched.')
  }

  const onCreateGroup = async () => {
    const result = await window.api.createGroup(newGroupName)
    if (!result.ok) {
      setStatus(result.message)
      return
    }
    const createdName = newGroupName.trim()
    setNewGroupName('')
    setStatus('Group created.')
    const refreshed = await loadGroups()
    const created = refreshed.find((group) => group.name === createdName)
    if (created) {
      setForm((current) => ({ ...current, groupId: created.id }))
    }
  }

  const onToggleSelect = (id) => {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id],
    )
  }

  const onFilterGroupChange = async (value) => {
    const parsed = value === '' ? null : Number(value)
    setFilterGroupId(parsed)
    await loadLinks(parsed)
  }

  const detectedBrowsersText =
    Object.keys(browserInfo.detected).length === 0
      ? 'Detected browsers: none (System Default still works).'
      : `Detected browsers: ${Object.keys(browserInfo.detected).sort().join(', ')}`

  return (
    <main className="min-h-screen bg-slate-100 p-6 text-slate-800">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-6 xl:grid-cols-[2fr,1fr]">
        <section className="rounded-2xl bg-white p-6 shadow-sm">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-3xl font-bold">Link Launcher</h1>
              <p className="text-sm text-slate-500">Create groups, save links, and launch them quickly.</p>
            </div>
            <button
              type="button"
              onClick={onLaunchVisible}
              className="rounded-lg bg-indigo-600 px-4 py-2 font-semibold text-white hover:bg-indigo-700"
            >
              Launch Visible
            </button>
          </div>

          <div className="mb-4 flex flex-wrap items-center gap-3">
            <label className="text-sm font-medium">Filter group</label>
            <select
              className="rounded-lg border border-slate-300 bg-white px-3 py-2"
              value={filterGroupId ?? ''}
              onChange={(event) => onFilterGroupChange(event.target.value)}
            >
              <option value="">{ALL_GROUPS}</option>
              {groups.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.name}
                </option>
              ))}
            </select>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="min-w-full border-collapse text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">Sel</th>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">URL</th>
                  <th className="px-4 py-3">Group</th>
                  <th className="px-4 py-3">Browser</th>
                </tr>
              </thead>
              <tbody>
                {links.length === 0 ? (
                  <tr>
                    <td className="px-4 py-8 text-center text-slate-500" colSpan={5}>
                      No links yet. Add one from the form.
                    </td>
                  </tr>
                ) : (
                  links.map((link) => (
                    <tr
                      key={link.id}
                      className={`border-t border-slate-200 ${selectedSet.has(link.id) ? 'bg-indigo-50' : 'bg-white'}`}
                      onClick={() =>
                        setForm({
                          id: link.id,
                          name: link.name,
                          url: link.url,
                          icon: link.icon || '',
                          groupId: link.groupId,
                          browser: link.browser,
                        })
                      }
                    >
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={selectedSet.has(link.id)}
                          onChange={() => onToggleSelect(link.id)}
                          onClick={(event) => event.stopPropagation()}
                        />
                      </td>
                      <td className="px-4 py-3 font-medium">{link.name}</td>
                      <td className="px-4 py-3 text-slate-600">{link.url}</td>
                      <td className="px-4 py-3">{link.groupName || NO_GROUP}</td>
                      <td className="px-4 py-3">{link.browser}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={onLaunchSelected}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 font-semibold hover:bg-slate-50"
            >
              Launch Selected
            </button>
            <button
              type="button"
              onClick={onDelete}
              className="rounded-lg border border-red-300 bg-red-50 px-4 py-2 font-semibold text-red-700 hover:bg-red-100"
            >
              Delete Selected
            </button>
            <button
              type="button"
              onClick={() => setForm(emptyForm)}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 font-semibold hover:bg-slate-50"
            >
              Clear Form
            </button>
          </div>
        </section>

        <section className="rounded-2xl bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-xl font-bold">Link Details</h2>
          <div className="space-y-3">
            <label className="block text-sm font-medium">
              Name*
              <input
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              />
            </label>

            <label className="block text-sm font-medium">
              URL*
              <input
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                value={form.url}
                onChange={(event) => setForm((current) => ({ ...current, url: event.target.value }))}
              />
            </label>

            <label className="block text-sm font-medium">
              Icon/Favicon (optional)
              <input
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                value={form.icon}
                onChange={(event) => setForm((current) => ({ ...current, icon: event.target.value }))}
              />
            </label>

            <label className="block text-sm font-medium">
              Group
              <select
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                value={form.groupId ?? ''}
                onChange={(event) =>
                  setForm((current) => ({ ...current, groupId: event.target.value === '' ? null : Number(event.target.value) }))
                }
              >
                <option value="">{NO_GROUP}</option>
                {groups.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </select>
            </label>

            <div className="grid grid-cols-[1fr,auto] gap-2">
              <input
                className="rounded-lg border border-slate-300 px-3 py-2"
                placeholder="New group name"
                value={newGroupName}
                onChange={(event) => setNewGroupName(event.target.value)}
              />
              <button
                type="button"
                onClick={onCreateGroup}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 font-semibold hover:bg-slate-50"
              >
                Create
              </button>
            </div>

            <label className="block text-sm font-medium">
              Browser
              <select
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                value={form.browser}
                onChange={(event) => setForm((current) => ({ ...current, browser: event.target.value }))}
              >
                {browserInfo.options.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>

            <p className="text-xs text-slate-500">{detectedBrowsersText}</p>

            <button
              type="button"
              onClick={onSave}
              className="w-full rounded-lg bg-indigo-600 px-4 py-2 font-semibold text-white hover:bg-indigo-700"
            >
              Save Link
            </button>

            <p className="min-h-10 whitespace-pre-line text-sm font-medium text-emerald-700">{status}</p>
          </div>
        </section>
      </div>
    </main>
  )
}

export default App
