import { useEffect, useMemo, useState } from 'react'
import './App.css'

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
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
          <div className="logo-section">
            <div className="logo-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
              </svg>
            </div>
            <div>
              <h1>Link Launcher</h1>
              <p>Organize and launch your favorite links effortlessly</p>
            </div>
          </div>
          <button type="button" onClick={onLaunchVisible} className="btn btn-primary glow">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="btn-icon">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
              <polyline points="15 3 21 3 21 9" />
              <line x1="10" y1="14" x2="21" y2="3" />
            </svg>
            Launch Visible
          </button>
        </div>
      </header>

      <main className="main-content">
        <section className="card links-section">
          <div className="section-header">
            <h2>Your Links</h2>
            <div className="filter-group">
              <label htmlFor="filter-select">Filter by group</label>
              <select
                id="filter-select"
                className="input-field"
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
          </div>

          <div className="table-container">
            <table className="modern-table">
              <thead>
                <tr>
                  <th className="col-select">Select</th>
                  <th className="col-name">Name</th>
                  <th className="col-url">URL</th>
                  <th className="col-group">Group</th>
                  <th className="col-browser">Browser</th>
                </tr>
              </thead>
              <tbody>
                {links.length === 0 ? (
                  <tr>
                    <td className="empty-state" colSpan={5}>
                      <div className="empty-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M13.828 10.172a4 4 0 0 0-5.656 0l-4 4a4 4 0 1 0 5.656 5.656l1.102-1.101m-.758-4.899a4 4 0 0 0 5.656 0l4-4a4 4 0 0 0-5.656-5.656l-1.1 1.1" />
                        </svg>
                      </div>
                      <p>No links yet. Add one from the form.</p>
                    </td>
                  </tr>
                ) : (
                  links.map((link) => (
                    <tr
                      key={link.id}
                      className={`link-row ${selectedSet.has(link.id) ? 'selected' : ''}`}
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
                      <td className="col-select">
                        <input
                          type="checkbox"
                          checked={selectedSet.has(link.id)}
                          onChange={() => onToggleSelect(link.id)}
                          onClick={(event) => event.stopPropagation()}
                          className="checkbox-custom"
                        />
                      </td>
                      <td className="col-name">
                        <span className="link-name">{link.name}</span>
                      </td>
                      <td className="col-url">
                        <span className="link-url">{link.url}</span>
                      </td>
                      <td className="col-group">
                        <span className="badge">{link.groupName || NO_GROUP}</span>
                      </td>
                      <td className="col-browser">
                        <span className="browser-tag">{link.browser}</span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="action-bar">
            <button type="button" onClick={onLaunchSelected} className="btn btn-secondary">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="btn-icon">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              Launch Selected
            </button>
            <button type="button" onClick={onDelete} className="btn btn-danger">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="btn-icon">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
              Delete Selected
            </button>
            <button type="button" onClick={() => setForm(emptyForm)} className="btn btn-ghost">
              Clear Form
            </button>
          </div>
        </section>

        <section className="card form-section">
          <div className="form-header">
            <h2>{form.id ? 'Edit Link' : 'Add New Link'}</h2>
            <div className="form-indicator"></div>
          </div>

          <div className="form-body">
            <div className="form-group">
              <label htmlFor="name-input">Link Name <span className="required">*</span></label>
              <input
                id="name-input"
                type="text"
                className="input-field"
                placeholder="e.g., Google Drive"
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              />
            </div>

            <div className="form-group">
              <label htmlFor="url-input">URL <span className="required">*</span></label>
              <input
                id="url-input"
                type="text"
                className="input-field"
                placeholder="https://example.com"
                value={form.url}
                onChange={(event) => setForm((current) => ({ ...current, url: event.target.value }))}
              />
            </div>

            <div className="form-group">
              <label htmlFor="icon-input">Icon/Favicon URL <span className="optional">(optional)</span></label>
              <input
                id="icon-input"
                type="text"
                className="input-field"
                placeholder="https://example.com/favicon.ico"
                value={form.icon}
                onChange={(event) => setForm((current) => ({ ...current, icon: event.target.value }))}
              />
            </div>

            <div className="form-group">
              <label htmlFor="group-select">Group</label>
              <select
                id="group-select"
                className="input-field"
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
            </div>

            <div className="form-group">
              <label>Create New Group</label>
              <div className="input-group">
                <input
                  type="text"
                  className="input-field input-inline"
                  placeholder="Enter group name"
                  value={newGroupName}
                  onChange={(event) => setNewGroupName(event.target.value)}
                />
                <button type="button" onClick={onCreateGroup} className="btn btn-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                </button>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="browser-select">Browser</label>
              <select
                id="browser-select"
                className="input-field"
                value={form.browser}
                onChange={(event) => setForm((current) => ({ ...current, browser: event.target.value }))}
              >
                {browserInfo.options.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
              <p className="helper-text">{detectedBrowsersText}</p>
            </div>

            <button type="button" onClick={onSave} className="btn btn-primary btn-full">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="btn-icon">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
                <polyline points="17 21 17 13 7 13 7 21" />
                <polyline points="7 3 7 8 15 8" />
              </svg>
              {form.id ? 'Update Link' : 'Save Link'}
            </button>

            {status && (
              <div className={`status-message ${status.includes('error') || status.includes('Select') ? 'error' : 'success'}`}>
                {status}
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  )
}

export default App