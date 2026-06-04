/**
 * FeaturesCache — carica web/data/features.json e fornisce helper per i privilegi.
 * Usato da sheet.js per renderizzare la sezione "Privilegi".
 */
const FeaturesCache = (() => {
  const CACHE_KEY = 'cz_features';
  const VERSION = 6;
  let _data = null;

  async function load() {
    if (_data) return _data;
    const cached = sessionStorage.getItem(CACHE_KEY);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        if (parsed.__v === VERSION) { _data = parsed; return _data; }
      } catch (_) {}
    }
    const res = await fetch('/data/features.json?v=6');
    if (!res.ok) throw new Error('Impossibile caricare features.json');
    _data = await res.json();
    try { sessionStorage.setItem(CACHE_KEY, JSON.stringify(_data)); } catch (_) {}
    return _data;
  }

  /** Ritorna i privilegi di una classe per un certo livello massimo. */
  function classFeatures(classValue, maxLevel) {
    if (!_data) return [];
    const all = _data.class_features?.[classValue] || [];
    return all.filter(f => f.level <= maxLevel);
  }

  /** Ritorna i privilegi di una sottoclasse per un certo livello massimo. */
  function subclassFeatures(subclassName, maxLevel) {
    if (!_data || !subclassName) return [];
    // Cerca match fuzzy (la sottoclasse potrebbe avere nome leggermente diverso)
    const key = _findSubclassKey(subclassName);
    if (!key) return [];
    const all = _data.subclass_features?.[key] || [];
    return all.filter(f => f.level <= maxLevel);
  }

  function _findSubclassKey(name) {
    if (!_data?.subclass_features) return null;
    const keys = Object.keys(_data.subclass_features);
    // Esatta
    if (keys.includes(name)) return name;
    // Case-insensitive
    const lower = name.toLowerCase();
    const exact = keys.find(k => k.toLowerCase() === lower);
    if (exact) return exact;
    // Partial match
    const partial = keys.find(k =>
      k.toLowerCase().includes(lower) || lower.includes(k.toLowerCase())
    );
    return partial || null;
  }

  /** Ritorna i tratti razziali per una razza. */
  function raceFeatures(raceName) {
    if (!_data || !raceName) return [];
    const key = _findRaceKey(raceName);
    return _data.race_features?.[key] || [];
  }

  function _findRaceKey(name) {
    if (!_data?.race_features) return null;
    const keys = Object.keys(_data.race_features);
    if (keys.includes(name)) return name;
    const lower = name.toLowerCase();
    return keys.find(k => k.toLowerCase() === lower || k.toLowerCase().includes(lower) || lower.includes(k.toLowerCase())) || null;
  }

  /** Ritorna i privilegi di un background. */
  function backgroundFeatures(bgName) {
    if (!_data || !bgName) return [];
    const key = _findBgKey(bgName);
    return _data.background_features?.[key] || [];
  }

  function _findBgKey(name) {
    if (!_data?.background_features) return null;
    const keys = Object.keys(_data.background_features);
    if (keys.includes(name)) return name;
    const lower = name.toLowerCase();
    return keys.find(k => k.toLowerCase() === lower || k.toLowerCase().includes(lower) || lower.includes(k.toLowerCase())) || null;
  }

  return { load, classFeatures, subclassFeatures, raceFeatures, backgroundFeatures };
})();
