LEVEL_OPTIONS = [
    'Primary school',
    'O level',
    'A level',
    'Tertiary education',
]


def normalize_education_level(level):
    if not level:
        return 'Primary school'

    normalized = str(level).strip().lower()

    if normalized in {'primary school', 'primary', 'school'}:
        return 'Primary school'
    if normalized in {'o level', 'o-level', 'ordinary level'}:
        return 'O level'
    if normalized in {'a level', 'a-level', 'advanced level'}:
        return 'A level'
    if normalized in {'tertiary education', 'tertiary', 'university', 'college'}:
        return 'Tertiary education'

    return 'Primary school'


def build_level_instruction(level):
    education_level = normalize_education_level(level)

    if education_level == 'Primary school':
        return (
            'Write for a primary school learner. Use simple vocabulary, short sentences, clear structure, and age-appropriate examples. '
            'Keep the content easy to follow and engaging.'
        )

    if education_level == 'O level':
        return (
            'Write for O level students. Use moderate vocabulary, structured paragraphs, logical flow, and exam-friendly language. '
            'Avoid overly complex phrasing while maintaining clarity and organisation.'
        )

    if education_level == 'A level':
        return (
            'Write for A level students. Use academic vocabulary, analytical reasoning, coherent argument structure, and mature expression. '
            'Show depth without becoming unnecessarily dense.'
        )

    return (
        'Write for tertiary education. Use advanced academic language, nuanced analysis, strong critical insight, and well-developed reasoning. '
        'Maintain depth, precision, and scholarly tone.'
    )
