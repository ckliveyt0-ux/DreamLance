document.addEventListener('DOMContentLoaded', function(){
  const form = document.getElementById('quoteForm');
  const status = document.getElementById('formStatus');

  async function showSubmittedModal(){
    const modal = document.createElement('div');
    modal.className = 'dl-modal';
    modal.innerHTML = `
      <div class="card">
        <h3>Request Submitted</h3>
        <p class="meta">Thanks — your request is submitted and pending review by our team.</p>
        <p style="color:var(--muted)">You will receive an email when a tailored estimate is ready.</p>
        <div class="actions">
          <button class="btn btn-primary" id="dlClose">Close</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector('#dlClose').addEventListener('click', ()=> modal.remove());
  }

  form.addEventListener('submit', async function(e){
    e.preventDefault();
    const formData = new FormData(form);
    const data = {
      name: formData.get('name') || 'Anonymous',
      email: formData.get('email') || '',
      interest: formData.get('interest'),
      message: formData.get('message') || ''
    };

    if(!data.email){
      status.textContent = 'Please provide a valid email so we can follow up.';
      status.style.color = 'crimson';
      return;
    }

    status.textContent = 'Submitting request…';
    status.style.color = 'var(--muted)';

    try{
      const res = await fetch('/api/requests', { method:'POST', headers:{ 'Content-Type':'application/json' }, body: JSON.stringify(data) });
      if(res.ok){
        status.textContent = 'Request submitted — awaiting admin estimate.';
        status.style.color = 'var(--teal)';
        showSubmittedModal();
        form.reset();
      } else {
        const j = await res.json();
        status.textContent = j.error || 'Submission failed';
        status.style.color = 'crimson';
      }
    }catch(err){
      status.textContent = 'Network error — could not submit.';
      status.style.color = 'crimson';
    }
  });

  // load jobs into jobsList
  const jobsContainer = document.getElementById('jobsList');
  if(jobsContainer){
    fetch('/api/jobs').then(r=>r.json()).then(data=>{
      const jobs = data.jobs || [];
      if(jobs.length === 0){ jobsContainer.innerHTML = '<p>No live jobs found.</p>'; return }
      const html = jobs.map(j=>`
        <article class="job-card" onclick="window.open('${j.url}', '_blank')" style="cursor: pointer;">
          <div class="job-card-header">
            <span class="job-tag">${j.type||'Full-time'}</span>
            <span class="company-logo-avatar">${j.company.charAt(0)}</span>
          </div>
          <h3>${j.title}</h3>
          <p class="company-name">${j.company}</p>
          <div class="job-card-footer">
            <span class="job-location">📍 ${j.location || 'Remote'}</span>
            <span class="apply-arrow">Apply Now →</span>
          </div>
        </article>
      `).join('\n');
      jobsContainer.innerHTML = html;
    }).catch(()=>{ jobsContainer.innerHTML = '<p>Unable to load jobs.</p>' });
  }

  // load news into newsList with filters
  let allNews = [];
  let currentFilter = 'all';
  
  function renderNews(filter = 'all'){
    const newsList = document.getElementById('newsList');
    let filtered = filter === 'all' ? allNews : allNews.filter(n => n.category === filter);
    if(filtered.length === 0){ newsList.innerHTML = '<p>No news found in this category.</p>'; return }
    const html = filtered.map(n=>{
      const pubDate = new Date(n.publishedAt).toLocaleDateString();
      return `
        <article class="news-card" onclick="window.open('${n.url}', '_blank')" style="cursor: pointer;">
          <div class="news-image" style="background-image:url('${n.image || 'https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&w=400&q=80'}')">&nbsp;</div>
          <div class="news-content">
            <div class="news-badge-container">
              <span class="news-category badge-${n.category}">${n.category}</span>
            </div>
            <h3>${n.title}</h3>
            <p>${n.description || 'Click to read more...'}</p>
            <div class="news-meta">
              <small>📰 ${n.source} · 📅 ${pubDate}</small>
              <span class="read-more">Read Article →</span>
            </div>
          </div>
        </article>
      `
    }).join('\n');
    newsList.innerHTML = html;
  }

  const newsContainer = document.getElementById('newsList');
  if(newsContainer){
    fetch('/api/news').then(r=>r.json()).then(data=>{
      allNews = data.news || [];
      renderNews('all');
    }).catch(()=>{ newsContainer.innerHTML = '<p>Unable to load news.</p>' });
  }

  // news filters
  const filterBtns = document.querySelectorAll('.filter-btn');
  filterBtns.forEach(btn => {
    btn.addEventListener('click', function(){
      filterBtns.forEach(b => b.classList.remove('active'));
      this.classList.add('active');
      currentFilter = this.dataset.filter;
      renderNews(currentFilter);
    });
  });

});

