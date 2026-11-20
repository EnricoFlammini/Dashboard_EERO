/**
 * eero Custom Dashboard & Management Suite - Frontend Utilities
 * Pure helper functions & formatting logic.
 */
const EeroUtils = {
  mergeModules(target, ...sources) {
    for (const source of sources) {
      if (!source) continue;
      Object.defineProperties(target, Object.getOwnPropertyDescriptors(source));
    }
    return target;
  },

  formatBytes(bytes, decimals = 1) {
    if (!bytes || bytes <= 0 || isNaN(bytes)) return '0 B';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    const idx = Math.min(i, sizes.length - 1);
    return parseFloat((bytes / Math.pow(k, idx)).toFixed(dm)) + ' ' + sizes[idx];
  },

  formatTrafficRate(mbps) {
    if (mbps === undefined || mbps === null || isNaN(mbps)) return '';
    const num = Number(mbps);
    if (num <= 0.05) return '';
    if (num >= 100) return Math.round(num) + 'M';
    return num.toFixed(1) + 'M';
  },

  formatSpeed(mbps) {
    return this.formatTrafficRate(mbps);
  },

  normalizeDnsUrl(url) {
    let clean = String(url || '').trim();
    if (!clean) return '';
    if (clean.includes('#')) clean = clean.split('#')[0];
    clean = clean.replace(/\/+$/, '');
    if (!clean.startsWith('http://') && !clean.startsWith('https://')) clean = 'http://' + clean;
    return clean;
  },

  renderSimpleMarkdown(md) {
    if (!md) return '';
    // Escape raw HTML entities to prevent XSS
    let text = String(md)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');

    // Inline styles first: links, bold, italic, code, horizontal rules
    text = text
      .replace(/\[(.*?)\]\((.*?)\)/g, (match, label, href) => {
        const cleanHref = (href || '').trim();
        if (/^(?:https?:\/\/|mailto:|\/(?!\/)|#)/i.test(cleanHref)) {
          return `<a href="${cleanHref}" target="_blank" rel="noopener noreferrer" class="text-sky-400 hover:text-sky-300 underline font-medium">${label}</a>`;
        }
        return `<span class="text-sky-400 font-medium">${label}</span>`;
      })
      .replace(/\*\*(.*?)\*\*/g, '<strong class="text-sky-300 font-semibold">$1</strong>')
      .replace(/\*(.*?)\*/g, '<em class="text-slate-300">$1</em>')
      .replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 rounded bg-slate-800 text-sky-300 font-mono text-[11px]">$1</code>')
      .replace(/---/g, '<hr class="border-slate-800 my-4"/>');

    const lines = text.split('\n');
    let out = [];
    let inUl = false;
    let inOl = false;
    let inSubUl = false;

    for (let i = 0; i < lines.length; i++) {
      let line = lines[i];
      let trimmed = line.trim();

      if (!trimmed) {
        if (inSubUl) { out.push('</ul>'); inSubUl = false; }
        if (inUl) { out.push('</ul>'); inUl = false; }
        if (inOl) { out.push('</ol>'); inOl = false; }
        continue;
      }

      if (/^###\s+/.test(trimmed)) {
        if (inSubUl) { out.push('</ul>'); inSubUl = false; }
        if (inUl) { out.push('</ul>'); inUl = false; }
        if (inOl) { out.push('</ol>'); inOl = false; }
        out.push(`<h4 class="text-sm font-bold text-sky-400 mt-4 mb-2">${trimmed.replace(/^###\s+/, '')}</h4>`);
        continue;
      }
      if (/^##\s+/.test(trimmed)) {
        if (inSubUl) { out.push('</ul>'); inSubUl = false; }
        if (inUl) { out.push('</ul>'); inUl = false; }
        if (inOl) { out.push('</ol>'); inOl = false; }
        out.push(`<h3 class="text-base font-bold text-white mt-5 mb-2">${trimmed.replace(/^##\s+/, '')}</h3>`);
        continue;
      }
      if (/^#\s+/.test(trimmed)) {
        if (inSubUl) { out.push('</ul>'); inSubUl = false; }
        if (inUl) { out.push('</ul>'); inUl = false; }
        if (inOl) { out.push('</ol>'); inOl = false; }
        out.push(`<h2 class="text-lg font-bold text-white mt-6 mb-3 border-b border-slate-800 pb-1">${trimmed.replace(/^#\s+/, '')}</h2>`);
        continue;
      }

      if (/^(?:[*-]|\d+\.)\s+/.test(trimmed)) {
        const isNum = /^\d+\.\s+/.test(trimmed);
        const isSub = line.search(/\S/) >= 4;
        const itemContent = trimmed.replace(/^(?:[*-]|\d+\.)\s+/, '');

        if (isSub) {
          if (!inSubUl) { out.push('<ul class="pl-5 space-y-1 my-1 list-circle text-slate-300">'); inSubUl = true; }
          out.push(`<li>${itemContent}</li>`);
        } else {
          if (inSubUl) { out.push('</ul>'); inSubUl = false; }
          if (isNum) {
            if (inUl) { out.push('</ul>'); inUl = false; }
            if (!inOl) { out.push('<ol class="pl-5 space-y-1.5 my-2 list-decimal text-slate-300">'); inOl = true; }
          } else {
            if (inOl) { out.push('</ol>'); inOl = false; }
            if (!inUl) { out.push('<ul class="pl-5 space-y-1.5 my-2 list-disc text-slate-300">'); inUl = true; }
          }
          out.push(`<li>${itemContent}</li>`);
        }
        continue;
      }

      if (inSubUl) { out.push('</ul>'); inSubUl = false; }
      if (inUl) { out.push('</ul>'); inUl = false; }
      if (inOl) { out.push('</ol>'); inOl = false; }

      if (/^&gt;\s+/.test(trimmed)) {
        out.push(`<blockquote class="border-l-4 border-sky-500 pl-3 py-1 my-2 text-slate-400 italic">${trimmed.replace(/^&gt;\s+/, '')}</blockquote>`);
        continue;
      }

      out.push(`<p class="my-2 text-slate-300 leading-relaxed">${trimmed}</p>`);
    }

    if (inSubUl) out.push('</ul>');
    if (inUl) out.push('</ul>');
    if (inOl) out.push('</ol>');

    return out.join('\n');
  },

  getBufferbloatGrade(speedtestObj) {
    const st = speedtestObj || (this && this.latestSpeedtest) || {};

    const gradeStyles = {
      'A+': {
        grade: 'A+',
        label: (this && this.t) ? this.t('bufferbloat.label_a_plus') : 'Eccellente',
        class: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30'
      },
      'A': {
        grade: 'A',
        label: (this && this.t) ? this.t('bufferbloat.label_a') : 'Molto Buono',
        class: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
      },
      'B': {
        grade: 'B',
        label: (this && this.t) ? this.t('bufferbloat.label_b') : 'Buono',
        class: 'bg-sky-500/15 text-sky-600 dark:text-sky-400 border-sky-500/30'
      },
      'C': {
        grade: 'C',
        label: (this && this.t) ? this.t('bufferbloat.label_c') : 'Discreto',
        class: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30'
      },
      'D': {
        grade: 'D',
        label: (this && this.t) ? this.t('bufferbloat.label_d') : 'Scarso',
        class: 'bg-orange-500/15 text-orange-600 dark:text-orange-400 border-orange-500/30'
      },
      'F': {
        grade: 'F',
        label: (this && this.t) ? this.t('bufferbloat.label_f') : 'Critico',
        class: 'bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30'
      }
    };

    let rawGrade = String(st.bufferbloat_grade || st.grade || '').trim().toUpperCase();
    if (gradeStyles[rawGrade]) {
      return gradeStyles[rawGrade];
    }

    const delta = (st.bufferbloat_delta_ms !== undefined && st.bufferbloat_delta_ms !== null)
      ? Number(st.bufferbloat_delta_ms)
      : (st.ping_under_load !== undefined && st.ping_under_load !== null && st.ping)
        ? Math.max(0, Number(st.ping_under_load) - Number(st.ping))
        : null;

    if (delta !== null && !isNaN(delta)) {
      if (delta <= 5) return gradeStyles['A+'];
      if (delta <= 15) return gradeStyles['A'];
      if (delta <= 30) return gradeStyles['B'];
      if (delta <= 60) return gradeStyles['C'];
      if (delta <= 120) return gradeStyles['D'];
      return gradeStyles['F'];
    }

    return null;
  },

  _fallbackCopyText(text, title, msg) {
    const el = document.createElement('textarea');
    el.value = text;
    el.setAttribute('readonly', '');
    el.style.position = 'absolute';
    el.style.left = '-9999px';
    document.body.appendChild(el);
    el.select();
    try {
      document.execCommand('copy');
      if (this && this.showToast) this.showToast(title, msg, 'success');
    } catch (err) {
      if (this && this.showToast) this.showToast('Error', 'Copy failed: ' + err, 'error');
    } finally {
      document.body.removeChild(el);
    }
  }
};

if (typeof window !== 'undefined') {
  window.EeroUtils = EeroUtils;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = EeroUtils;
}
