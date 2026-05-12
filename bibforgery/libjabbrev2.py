import re

# ── Exact matches for brand names, subtitle-truncated journals, or
EXACT_ABBREV = {
    'chemphyschem':                                              'ChemPhysChem',
    'chemistryselect':                                           'ChemistrySelect',
    'physica e: low-dimensional systems and nanostructures':     'Physica E',
    'fuel':        'Fuel',
    'matter':      'Matter',
    'molecules':   'Molecules',
    'nanoscale':   'Nanoscale',
    'nanomaterials': 'Nanomaterials',
    'heliyon':     'Heliyon',
    'molbank':     'Molbank',
    'genes':       'Genes',
    'atoms':       'Atoms',
    'chemosensors': 'Chemosensors',
    'agriculture': 'Agriculture',
    'microstructures': 'Microstructures',
    'acs sustainable chemistry & engineering':  'ACS Sustain. Chem. Eng.',
    'acs sustainable chemistry and engineering': 'ACS Sustain. Chem. Eng.',
    'acs sustainable chem. eng.':               'ACS Sustain. Chem. Eng.',
}

# ── Word-level abbreviations (ISO 4 / CASSI conventions) ─────────
WORD_ABBREV = {
    # Journal type
    'journal':          'J.',
    'letters':          'Lett.',
    'letter':           'Lett.',
    'reviews':          'Rev.',
    'review':           'Rev.',
    'reports':          'Rep.',
    'report':           'Rep.',
    'communications':   'Commun.',
    'communication':    'Commun.',
    'proceedings':      'Proc.',
    'transactions':     'Trans.',
    'bulletin':         'Bull.',
    'accounts':         'Acc.',
    'advances':         'Adv.',
    'advanced':         'Adv.',
    'topics':           'Top.',
    'edition':          'Ed.',
    'current':          'Curr.',
    'today':            'Today',
    'select':           'Sel.',
    'open':             'Open',
    'new':              'New',
    # Disciplines
    'chemistry':        'Chem.',
    'chemical':         'Chem.',
    'chemie':           'Chem.',       # German
    'physics':          'Phys.',
    'physical':         'Phys.',
    'physica':          'Physica',
    'biology':          'Biol.',
    'biological':       'Biol.',
    'biochemistry':     'Biochem.',
    'biochemical':      'Biochem.',
    'biophysics':       'Biophys.',
    'biophysical':      'Biophys.',
    'bioinformatics':   'Bioinforma.',
    'bioorganic':       'Bioorg.',
    'mathematics':      'Math.',
    'mathematical':     'Math.',
    # Subfields
    'organic':          'Org.',
    'inorganic':        'Inorg.',
    'analytical':       'Anal.',
    'analysis':         'Anal.',
    'applied':          'Appl.',
    'computational':    'Comput.',
    'computation':      'Comput.',
    'theoretical':      'Theor.',
    'theory':           'Theory',
    'quantum':          'Quantum',
    'nuclear':          'Nucl.',
    'atomic':           'At.',
    'molecular':        'Mol.',
    'supramolecular':   'Supramol.',
    'macromolecular':   'Macromol.',
    'organometallic':   'Organomet.',
    'coordination':     'Coord.',
    'electrochemistry': 'Electrochem.',
    'electrochemical':  'Electrochem.',
    'photochemistry':   'Photochem.',
    'photochemical':    'Photochem.',
    'photocatalysis':   'Photocatal.',
    'spectroscopy':     'Spectrosc.',
    'spectroscopic':    'Spectrosc.',
    'chromatography':   'Chromatogr.',
    # Materials & structure
    'materials':        'Mater.',
    'material':         'Mater.',
    'polymer':          'Polym.',
    'polymers':         'Polym.',
    'ceramic':          'Ceram.',
    'ceramics':         'Ceram.',
    'crystal':          'Cryst.',
    'crystallography':  'Cryst.',
    'surface':          'Surf.',
    'surfaces':         'Surf.',
    'interface':        'Interface',
    'interfaces':       'Interfaces',
    'liquid':           'Liq.',
    'solid':            'Solid',
    'solids':           'Solids',
    'nanostructure':    'Nanostruct.',
    'nanostructures':   'Nanostruct.',
    'nanotechnology':   'Nanotechnol.',
    'diamond':          'Diamond',
    'related':          'Relat.',
    'condensed':        'Condens.',
    'dimensional':      'Dimens.',
    'low':              'Low',
    'high':             'High',
    'soft':             'Soft',
    'structural':       'Struct.',
    'structure':        'Struct.',
    'structures':       'Struct.',
    # Properties / phenomena
    'optical':          'Opt.',
    'magnetic':         'Magn.',
    'electronic':       'Electron.',
    'thermal':          'Therm.',
    'thermodynamics':   'Thermodyn.',
    'kinetics':         'Kinet.',
    # Fields / domains
    'catalysis':        'Catal.',
    'catalytic':        'Catal.',
    'environmental':    'Environ.',
    'energy':           'Energy',
    'atmospheric':      'Atmos.',
    'atmosphere':       'Atmos.',
    'earth':            'Earth',
    'space':            'Space',
    'astronomy':        'Astron.',
    'astronomical':     'Astron.',
    'astrophysics':     'Astrophys.',
    'astrophysical':    'Astrophys.',
    'geochemistry':     'Geochem.',
    'geophysics':       'Geophys.',
    'engineering':      'Eng.',
    'technology':       'Technol.',
    'industrial':       'Ind.',
    'research':         'Res.',
    'science':          'Sci.',
    'sciences':         'Sci.',
    'systems':          'Syst.',
    'system':           'Syst.',
    'methods':          'Methods',
    'modeling':         'Model.',
    'modelling':        'Model.',
    'simulation':       'Simul.',
    'synthesis':        'Synth.',
    # Biology / medicine
    'medicinal':        'Med.',
    'medicine':         'Med.',
    'medical':          'Med.',
    'pharmaceutical':   'Pharm.',
    'pharmacology':     'Pharmacol.',
    'toxicology':       'Toxicol.',
    'heterocyclic':     'Heterocycl.',
    # Institutions / geography
    'american':         'Am.',
    'international':    'Int.',
    'european':         'Eur.',
    'asian':            'Asian',
    'royal':            'R.',
    'national':         'Natl.',
    'society':          'Soc.',
    'academy':          'Acad.',
    'institute':        'Inst.',
    # German
    'angewandte':       'Angew.',
    'zeitschrift':      'Z.',
    'berichte':         'Ber.',
    # Other
    'pure':             'Pure',
    'sustainable':      'Sustain.',
    'sustainability':   'Sustain.',
    'green':            'Green',
    'clean':            'Clean',
    'natural':          'Nat.',
    'nature':           'Nature',
    'matter':           'Matter',
    'rapid':            'Rapid',
    'accounts':         'Acc.',
    'separation':       'Sep.',
    'purification':     'Purif.',
}

# ── Words to drop entirely ────────────────────────────────────────
DROP_WORDS = {
    'the', 'and', 'of', 'in', 'for', 'an', 'on', 'at', 'to',
    'with', 'by', '&',
}

# ── Main function ─────────────────────────────────────────────────
def jabbreviation2(journal):
    jl = journal.strip().lower()

    # Layer 1: exact match
    if jl in EXACT_ABBREV:
        return EXACT_ABBREV[jl]

    # Normalize separators: " - " and commas → space; colon → space
    name = re.sub(r'\s+-\s+', ' ', journal)
    name = re.sub(r',\s*',    ' ', name)
    name = re.sub(r'\s*:\s*', ' ', name)

    tokens = name.split()
    n = len(tokens)
    result = []

    for i, token in enumerate(tokens):
        tl = token.lower()

        # Drop articles/prepositions
        if tl in DROP_WORDS:
            continue

        # "A" is an indefinite article unless it is the final token
        # (final token = section letter, e.g. "J. Phys. Chem. A")
        if token == 'A' and i < n - 1:
            continue

        # All-caps token → acronym or section letter, keep as-is
        if token.isupper():
            result.append(token)
            continue

        # Hyphenated compound word: abbreviate each part separately
        if '-' in token:
            parts = token.split('-')
            abbr = '-'.join(WORD_ABBREV.get(p.lower(), p) for p in parts)
            result.append(abbr)
            continue

        # Normal word lookup
        result.append(WORD_ABBREV.get(tl, token))

    return ' '.join(result)
