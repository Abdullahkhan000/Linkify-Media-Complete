/* Presentation only: retain the original text nodes for assistive technology. */
(() => {
    const hero = document.querySelector('.ticker-track')?.closest('section');
    if (!hero || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const heading = hero.querySelector('h1');
    const description = hero.querySelector('p.reveal');
    if (!heading || !description) return;

    const groups = [];
    const prepare = (node, speed) => {
        const text = node.textContent;
        if (!text.trim()) return;
        const wrapper = document.createElement('span');
        wrapper.className = 'hero-typing';
        const source = document.createElement('span');
        source.className = 'hero-typing-source';
        const visual = document.createElement('span');
        visual.setAttribute('aria-hidden', 'true');
        const characters = [];
        // Keep words together so normal paragraph wrapping remains readable.
        for (const part of text.split(/(\s+)/)) {
            if (/^\s+$/.test(part)) {
                visual.append(document.createTextNode(part));
                continue;
            }
            const word = document.createElement('span');
            word.className = 'hero-typing-word';
            for (const character of Array.from(part)) {
                const letter = document.createElement('span');
                letter.className = 'hero-typing-letter';
                letter.textContent = character;
                word.append(letter);
                characters.push(letter);
            }
            visual.append(word);
        }
        node.before(wrapper);
        source.append(node);
        wrapper.append(source, visual);
        groups.push({ characters, speed });
    };

    for (const node of Array.from(heading.childNodes)) {
        if (node.nodeType === Node.TEXT_NODE) prepare(node, 70);
        else if (node.nodeType === Node.ELEMENT_NODE && node.tagName !== 'BR') {
            for (const text of Array.from(node.childNodes)) {
                if (text.nodeType === Node.TEXT_NODE) prepare(text, 70);
            }
        }
    }
    for (const node of Array.from(description.childNodes)) {
        if (node.nodeType === Node.TEXT_NODE) prepare(node, 16);
    }

    let groupIndex = 0;
    let characterIndex = 0;
    let previous;
    const reveal = () => {
        previous?.classList.remove('hero-typing-current');
        const group = groups[groupIndex];
        if (!group) return;
        const letter = group.characters[characterIndex++];
        if (!letter) {
            groupIndex++;
            characterIndex = 0;
            window.setTimeout(reveal, 180);
            return;
        }
        letter.classList.add('hero-typing-visible', 'hero-typing-current');
        previous = letter;
        window.setTimeout(reveal, group.speed);
    };
    window.setTimeout(reveal, 500);
})();
