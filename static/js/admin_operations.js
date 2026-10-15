// Use textContent for every value received from the API; never interpolate user HTML.
let userPage = 1;
let auditPage = 1;
const notice = document.getElementById('notice');
async function api(path, options = {}) {
  const response = await fetch(`/api/admin/${path}`, options);
  if (response.status === 401) { window.location.assign('/admin/login'); throw new Error('Please sign in'); }
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : (data.detail?.message || 'Request failed'));
  return data;
}
function cell(row, value) {
  const td = document.createElement('td');
  td.textContent = value ?? '—';
  td.style.padding = '0.7rem';
  row.appendChild(td);
  return td;
}
async function load() {
  try {
    const [system, users, audit] = await Promise.all([
      api('system'), api(`users?page=${userPage}`), api(`audit?page=${auditPage}`)
    ]);
    const summary = document.getElementById('system'); summary.replaceChildren();
    for (const [label, value] of [['Printer agent', system.agent_online ? 'Online' : 'Offline'],
      ['Failed prints', system.failed_prints], ['Payment reviews', system.payment_anomalies]]) {
      const stat = document.createElement('div'); stat.className = 'system-stat';
      const caption = document.createElement('span'); caption.className = 'system-label'; caption.textContent = label;
      const number = document.createElement('span'); number.className = 'system-value'; number.textContent = value;
      stat.append(caption, number); summary.appendChild(stat);
    }
    document.getElementById('pool-details').textContent = system.database_pool;
    const body = document.getElementById('users'); body.replaceChildren();
    for (const user of users.items) {
      const row = document.createElement('tr');
      cell(row, user.id); cell(row, user.username); cell(row, user.email); cell(row, user.is_active ? 'Enabled' : 'Suspended');
      const button = document.createElement('button');
      button.textContent = user.is_active ? 'Suspend' : 'Enable';
      button.addEventListener('click', async () => {
        if (!window.confirm(`${button.textContent} access for ${user.username}?`)) return;
        button.disabled = true;
        try {
          await api(`users/${user.id}/access`, {
            method: 'PATCH', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({is_active: !user.is_active, reason: 'Administrative access change'})
          });
          notice.textContent = 'User access updated'; await load();
        } catch (error) { notice.textContent = error.message; button.disabled = false; }
      });
      cell(row, '').appendChild(button); body.appendChild(row);
    }
    document.getElementById('page').textContent = `Page ${userPage} of ${Math.max(1, users.pages)}`;
    document.getElementById('previous').disabled = userPage === 1;
    document.getElementById('next').disabled = userPage >= users.pages;
    const history = document.getElementById('audit'); history.replaceChildren();
    for (const item of audit.items) {
      const row = document.createElement('tr');
      cell(row, new Date(item.created_at).toLocaleString()); cell(row, item.actor_id);
      cell(row, item.action); cell(row, item.target_id); cell(row, item.request_id); history.appendChild(row);
    }
    document.getElementById('audit-page').textContent = `Page ${auditPage} of ${Math.max(1, audit.pages)}`;
    document.getElementById('audit-previous').disabled = auditPage === 1;
    document.getElementById('audit-next').disabled = auditPage >= audit.pages;
  } catch (error) { notice.textContent = error.message; }
}
document.getElementById('previous').addEventListener('click', () => { userPage--; load(); });
document.getElementById('next').addEventListener('click', () => { userPage++; load(); });
document.getElementById('audit-previous').addEventListener('click', () => { auditPage--; load(); });
document.getElementById('audit-next').addEventListener('click', () => { auditPage++; load(); });
load();
