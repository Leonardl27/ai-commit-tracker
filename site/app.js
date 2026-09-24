/* ===== AI Commit Tracker Dashboard ===== */

const MODEL_COLORS = {
  claude: '#d97706',
  openai_codex: '#3b82f6',
  gemini: '#10b981',
  cursor: '#a855f7',
};

const MODEL_LABELS = {
  claude: 'Claude',
  openai_codex: 'OpenAI Codex',
  gemini: 'Gemini',
  cursor: 'Cursor',
};

const MODELS = Object.keys(MODEL_COLORS);

function formatNumber(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return n.toLocaleString();
}

function formatStars(n) {
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'k';
  return n.toString();
}

function timeAgo(isoString) {
  const diff = Date.now() - new Date(isoString).getTime();
  const hours = Math.floor(diff / 3_600_000);
  if (hours < 1) return 'just now';
  if (hours < 24) return hours + 'h ago';
  const days = Math.floor(hours / 24);
  return days + 'd ago';
}

/* ---------- Data Loading ---------- */

async function loadData() {
  try {
    const resp = await fetch('data.json');
    if (!resp.ok) throw new Error('Failed to load data');
    return await resp.json();
  } catch (err) {
    console.error('Could not load data:', err);
    return null;
  }
}

/* ---------- Render Functions ---------- */

function renderSummaryCards(totals, lastUpdated) {
  document.getElementById('total-commits').textContent = formatNumber(totals.commits);
  document.getElementById('total-repos').textContent = formatNumber(totals.repos);
  document.getElementById('total-models').textContent = totals.models;
  document.getElementById('days-tracked').textContent = totals.days_tracked;
  document.getElementById('last-updated').textContent = 'Updated ' + timeAgo(lastUpdated);
}

function renderShareDoughnut(timeSeries) {
  // Aggregate totals across all days
  const totals = {};
  MODELS.forEach(m => { totals[m] = 0; });
  timeSeries.forEach(day => {
    MODELS.forEach(m => { totals[m] += (day[m] || 0); });
  });

  const activeModels = MODELS.filter(m => totals[m] > 0);
  if (activeModels.length === 0) return;

  new Chart(document.getElementById('chart-share-doughnut'), {
    type: 'doughnut',
    data: {
      labels: activeModels.map(m => MODEL_LABELS[m]),
      datasets: [{
        data: activeModels.map(m => totals[m]),
        backgroundColor: activeModels.map(m => MODEL_COLORS[m]),
        borderWidth: 2,
        borderColor: '#fff',
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { padding: 16, usePointStyle: true, pointStyleWidth: 10 },
        },
      },
      cutout: '60%',
    },
  });
}

function renderShareTimeline(timeSeries) {
  if (timeSeries.length === 0) return;

  const labels = timeSeries.map(d => d.date);
  const activeModels = MODELS.filter(m => timeSeries.some(d => (d[m] || 0) > 0));

  const datasets = activeModels.map(m => ({
    label: MODEL_LABELS[m],
    data: timeSeries.map(d => d[m] || 0),
    backgroundColor: MODEL_COLORS[m] + '33',
    borderColor: MODEL_COLORS[m],
    borderWidth: 2,
    fill: true,
    tension: 0.3,
    pointRadius: timeSeries.length > 30 ? 0 : 3,
  }));

  new Chart(document.getElementById('chart-share-time'), {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            maxTicksLimit: 10,
            callback: function(val) {
              const d = this.getLabelForValue(val);
              return d.slice(5); // MM-DD
            },
          },
        },
        y: { beginAtZero: true, grid: { color: '#f3f4f6' } },
      },
      plugins: {
        legend: {
          position: 'top',
          labels: { usePointStyle: true, pointStyleWidth: 10 },
        },
      },
    },
  });
}

function renderTopRepos(repos) {
  if (repos.length === 0) return;

  // Bar chart
  const labels = repos.map(r => r.repo.split('/')[1]); // short name
  const activeModels = MODELS.filter(m => repos.some(r => (r.by_model[m] || 0) > 0));

  const datasets = activeModels.map(m => ({
    label: MODEL_LABELS[m],
    data: repos.map(r => r.by_model[m] || 0),
    backgroundColor: MODEL_COLORS[m],
    borderRadius: 4,
  }));

  new Chart(document.getElementById('chart-top-repos'), {
    type: 'bar',
    data: { labels, datasets },
    options: {
      indexAxis: 'y',
      responsive: true,
      scales: {
        x: { stacked: true, grid: { color: '#f3f4f6' } },
        y: { stacked: true, grid: { display: false } },
      },
      plugins: {
        legend: {
          position: 'top',
          labels: { usePointStyle: true, pointStyleWidth: 10 },
        },
      },
    },
  });

  // Table
  const tbody = document.querySelector('#table-top-repos tbody');
  repos.forEach((r, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td><a href="https://github.com/${r.repo}" target="_blank" rel="noopener">${r.repo}</a></td>
      <td><span class="lang-badge">${r.language}</span></td>
      <td class="stars-cell">${formatStars(r.stars)}</td>
      <td><strong>${r.total}</strong></td>
    `;
    tbody.appendChild(tr);
  });
}

function renderRisingRepos(repos) {
  const tbody = document.querySelector('#table-rising-repos tbody');
  if (repos.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#9ca3af;">No data yet</td></tr>';
    return;
  }
  repos.forEach((r, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td><a href="https://github.com/${r.repo}" target="_blank" rel="noopener">${r.repo}</a></td>
      <td><span class="lang-badge">${r.language}</span></td>
      <td class="stars-cell">${formatStars(r.stars)}</td>
      <td><strong>${r.recent}</strong></td>
      <td>${r.total}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderLanguages(breakdown) {
  const langs = Object.keys(breakdown);
  if (langs.length === 0) return;

  const activeModels = MODELS.filter(m => langs.some(l => (breakdown[l][m] || 0) > 0));

  const datasets = activeModels.map(m => ({
    label: MODEL_LABELS[m],
    data: langs.map(l => breakdown[l][m] || 0),
    backgroundColor: MODEL_COLORS[m],
    borderRadius: 4,
  }));

  new Chart(document.getElementById('chart-languages'), {
    type: 'bar',
    data: { labels: langs, datasets },
    options: {
      indexAxis: 'y',
      responsive: true,
      scales: {
        x: { stacked: true, grid: { color: '#f3f4f6' } },
        y: { stacked: true, grid: { display: false } },
      },
      plugins: {
        legend: {
          position: 'top',
          labels: { usePointStyle: true, pointStyleWidth: 10 },
        },
      },
    },
  });
}

function renderAiVsHuman(repos) {
  if (!repos || repos.length === 0) return;

  const labels = repos.map(r => r.repo.split('/')[1]);

  new Chart(document.getElementById('chart-ai-vs-human'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'AI Commits',
          data: repos.map(r => r.ai_commits),
          backgroundColor: '#6366f1',
          borderRadius: 4,
        },
        {
          label: 'Human Commits',
          data: repos.map(r => r.human_commits),
          backgroundColor: '#e5e7eb',
          borderRadius: 4,
        },
      ],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      scales: {
        x: { stacked: true, grid: { color: '#f3f4f6' } },
        y: { stacked: true, grid: { display: false } },
      },
      plugins: {
        legend: {
          position: 'top',
          labels: { usePointStyle: true, pointStyleWidth: 10 },
        },
        tooltip: {
          callbacks: {
            afterBody: function(items) {
              const idx = items[0].dataIndex;
              const r = repos[idx];
              return `AI share: ${r.ai_percentage}%`;
            },
          },
        },
        // Percentage labels using datalabels-like approach via custom plugin
      },
    },
    plugins: [{
      id: 'aiPercentLabels',
      afterDatasetsDraw(chart) {
        const { ctx } = chart;
        const meta = chart.getDatasetMeta(1); // human commits (last stacked segment)
        ctx.save();
        ctx.font = '600 12px Inter, sans-serif';
        ctx.fillStyle = '#6366f1';
        ctx.textBaseline = 'middle';
        meta.data.forEach((bar, i) => {
          const pct = repos[i].ai_percentage;
          const x = bar.x + 8;
          const y = bar.y;
          ctx.fillText(pct + '%', x, y);
        });
        ctx.restore();
      },
    }],
  });
}

/* ---------- Init ---------- */

async function init() {
  const data = await loadData();
  if (!data) {
    document.querySelector('main').innerHTML =
      '<div class="empty-state"><h3>No data yet</h3><p>Run the data collection script to populate the dashboard.</p></div>';
    return;
  }

  renderSummaryCards(data.totals, data.last_updated);
  renderShareDoughnut(data.model_share_over_time);
  renderShareTimeline(data.model_share_over_time);
  renderTopRepos(data.top_repos);
  renderAiVsHuman(data.ai_vs_human);
  renderRisingRepos(data.rising_repos);
  renderLanguages(data.language_breakdown);
}

init();
