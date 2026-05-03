/* ─────────────────────────────────────────────────────────────
   PriceOptima · script.js
   Wired to Flask /compare (POST) → app.py response shape:
   {
     product_name, source_platform, source_url,
     amazon:   { name, price, url, platform } | null,
     flipkart: { ... } | null,
     croma:    { ... } | null,
     reliance: { ... } | null,
     best_price: { site, price, url } | null
   }
───────────────────────────────────────────────────────────── */

const API_BASE = 'http://localhost:8000';

// ── DOM refs ──────────────────────────────────────────────────
const form          = document.getElementById('compare-form');
const input         = document.getElementById('product-url');
const compareBtn    = document.getElementById('compare-btn');
const resultsArea   = document.getElementById('results-area');
const loader        = document.getElementById('loader');
const errorMsg      = document.getElementById('error-msg');
const errorText     = document.getElementById('error-text');
const dataView      = document.getElementById('data-view');
const resName       = document.getElementById('res-product-name');
const bestBanner    = document.getElementById('best-deal-banner');
const bestSite      = document.getElementById('best-site');
const bestPrice     = document.getElementById('best-price');
const bestLink      = document.getElementById('best-deal-link');
const platformsGrid = document.getElementById('platforms-grid');
const newSearchBtn  = document.getElementById('new-search-btn');

// ── Platform display config ───────────────────────────────────
const PLATFORM_META = {
    amazon:   { label: 'Amazon',           emoji: '🛒' },
    flipkart: { label: 'Flipkart',         emoji: '🛍️' },
    croma:    { label: 'Croma',            emoji: '📦' },
    reliance: { label: 'Reliance Digital', emoji: '📱' },
};

// ── Helpers ───────────────────────────────────────────────────
function formatPrice(price) {
    if (!price && price !== 0) return null;
    return '₹' + Number(price).toLocaleString('en-IN');
}

function showSection(el) { el.classList.remove('hidden'); }
function hideSection(el) { el.classList.add('hidden'); }

function resetResults() {
    hideSection(loader);
    hideSection(errorMsg);
    hideSection(dataView);
    platformsGrid.innerHTML = '';
    hideSection(bestBanner);
    resName.textContent = '';
}

function showError(message) {
    hideSection(loader);
    errorText.textContent = message || 'An unexpected error occurred. Please try again.';
    showSection(errorMsg);
}

function setLoading(on) {
    compareBtn.disabled = on;
    if (on) {
        showSection(loader);
        hideSection(errorMsg);
        hideSection(dataView);
    } else {
        hideSection(loader);
    }
}

// ── Build a platform card ─────────────────────────────────────
function buildCard(platformKey, result, bestPlatformKey) {
    const meta      = PLATFORM_META[platformKey] || { label: platformKey, emoji: '🏪' };
    const isBest    = platformKey === bestPlatformKey;
    const hasResult = result && result.price;

    const card = document.createElement('div');
    card.className = 'platform-card' + (isBest ? ' best-card' : '') + (!hasResult ? ' not-found' : '');

    const nameEl = document.createElement('p');
    nameEl.className = 'card-platform-name';
    nameEl.textContent = meta.label;
    card.appendChild(nameEl);

    const priceEl = document.createElement('p');
    if (hasResult) {
        priceEl.className = 'card-price';
        priceEl.textContent = formatPrice(result.price);
    } else {
        priceEl.className = 'card-price not-found-text';
        priceEl.textContent = 'Not available';
    }
    card.appendChild(priceEl);

    // Savings badge — shown on best card when multiple prices found
    if (isBest && result._savings > 0) {
        const badge = document.createElement('span');
        badge.className = 'card-savings';
        badge.innerHTML = `<i class="ph-fill ph-tag"></i> Save ${formatPrice(result._savings)}`;
        card.appendChild(badge);
    }

    // Buy button
    if (hasResult && result.url) {
        const link = document.createElement('a');
        link.className = 'card-link';
        link.href       = result.url;
        link.target     = '_blank';
        link.rel        = 'noopener';
        link.innerHTML  = `Buy <i class="ph ph-arrow-up-right"></i>`;
        card.appendChild(link);
    }

    return card;
}

// ── Render results ────────────────────────────────────────────
function renderResults(data) {
    // Product name
    resName.textContent = data.product_name || 'Product';

    // Determine best platform key
    let bestKey = null;
    if (data.best_price && data.best_price.site) {
        // Match site name back to our key
        bestKey = Object.keys(PLATFORM_META).find(
            k => PLATFORM_META[k].label.toLowerCase() === data.best_price.site.toLowerCase()
        ) || null;
    }

    // Calculate savings: difference between max and min real price
    const realPrices = ['amazon', 'flipkart', 'croma', 'reliance']
        .map(k => data[k]?.price)
        .filter(p => p != null && p > 0);

    const maxPrice = realPrices.length ? Math.max(...realPrices) : 0;
    const minPrice = realPrices.length ? Math.min(...realPrices) : 0;
    const savings  = maxPrice - minPrice;

    // Attach savings to best platform result for the card to use
    if (bestKey && data[bestKey]) {
        data[bestKey]._savings = savings;
    }

    // Best deal banner
    if (data.best_price) {
        bestSite.textContent  = data.best_price.site;
        bestPrice.textContent = formatPrice(data.best_price.price);
        bestLink.href         = data.best_price.url || '#';
        showSection(bestBanner);
    } else {
        hideSection(bestBanner);
    }

    // Platform cards — always show all 4 platforms
    platformsGrid.innerHTML = '';
    ['amazon', 'flipkart', 'croma', 'reliance'].forEach(key => {
        const card = buildCard(key, data[key], bestKey);
        platformsGrid.appendChild(card);
    });

    showSection(dataView);
}

// ── Submit handler ────────────────────────────────────────────
form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const url = input.value.trim();
    if (!url) return;

    resetResults();
    showSection(resultsArea);
    setLoading(true);

    try {
        const res = await fetch(`${API_BASE}/compare`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ url }),
        });

        // Handle non-2xx HTTP errors
        if (!res.ok) {
            let errMsg = `Server error (${res.status})`;
            try {
                const errData = await res.json();
                if (errData.error) errMsg = errData.error;
            } catch (_) {}
            showError(errMsg);
            return;
        }

        const data = await res.json();

        // Backend returned an error object
        if (data.error) {
            showError(data.error);
            return;
        }

        // No prices found at all
        const anyPrice = ['amazon','flipkart','croma','reliance'].some(k => data[k]?.price);
        if (!anyPrice && !data.product_name) {
            showError('Could not find any pricing data for this product. Try a different URL.');
            return;
        }

        renderResults(data);

    } catch (err) {
        console.error('[PriceOptima]', err);

        if (err.name === 'TypeError' && err.message.includes('fetch')) {
            showError('Cannot reach the server. Make sure the backend is running on port 8000.');
        } else {
            showError('Something went wrong. Please try again.');
        }
    } finally {
        setLoading(false);
    }
});

// ── "Compare another product" button ─────────────────────────
newSearchBtn.addEventListener('click', () => {
    hideSection(resultsArea);
    resetResults();
    input.value = '';
    input.focus();
    window.scrollTo({ top: 0, behavior: 'smooth' });
});

// ── Particle Animation ────────────────────────────────────────
(function initParticles() {
    const canvas = document.getElementById('particles');
    const ctx    = canvas.getContext('2d');

    // Colorful tick marks like Antigravity — red, blue, yellow, green
    const COLORS = [
        [220,  53,  69],  // red
        [ 37, 99, 235],   // blue
        [234, 179,   8],  // yellow
        [ 22, 163,  74],  // green
        [107,  33, 168],  // purple
    ];

    function resize() {
        canvas.width  = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    const PARTICLE_COUNT = 180;
    const particles = [];

    for (let i = 0; i < PARTICLE_COUNT; i++) {
        const color = COLORS[Math.floor(Math.random() * COLORS.length)];
        particles.push({
            x:      Math.random() * window.innerWidth,
            y:      Math.random() * window.innerHeight,
            vx:     (Math.random() - 0.5) * 0.5,
            vy:     (Math.random() - 0.5) * 0.5,
            // Tick mark properties
            len:    3 + Math.random() * 5,    // length of dash
            angle:  Math.random() * Math.PI,  // rotation of tick
            color:  color,
            alpha:  0.25 + Math.random() * 0.45,
        });
    }

    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        particles.forEach(p => {
            // Drift
            p.x += p.vx;
            p.y += p.vy;
            p.angle += 0.003;

            // Wrap around edges
            if (p.x < -20)               p.x = canvas.width  + 20;
            if (p.x > canvas.width  + 20) p.x = -20;
            if (p.y < -20)               p.y = canvas.height + 20;
            if (p.y > canvas.height + 20) p.y = -20;

            // Draw tick / dash
            const [r, g, b] = p.color;
            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.rotate(p.angle);
            ctx.strokeStyle = `rgba(${r},${g},${b},${p.alpha})`;
            ctx.lineWidth   = 1.8;
            ctx.lineCap     = 'round';
            ctx.beginPath();
            ctx.moveTo(-p.len / 2, 0);
            ctx.lineTo( p.len / 2, 0);
            ctx.stroke();
            ctx.restore();
        });

        requestAnimationFrame(draw);
    }

    draw();
})();
