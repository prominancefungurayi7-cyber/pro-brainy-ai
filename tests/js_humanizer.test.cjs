const { test } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const vm = require('node:vm');

const script = fs.readFileSync('static/js/humanizer.js', 'utf8');

async function runStream(events, splitEvery = 7) {
    const file = { name: 'sample.docx' };
    let submitHandler;
    let downloads = 0;
    const elements = {
        'humanizer-form': { action: '/humanizer', addEventListener: (_name, handler) => { submitHandler = handler; } },
        file: { files: [file] },
        'humanizer-progress': { hidden: true, classList: { add() {}, remove() {} } },
        'humanizer-progress-bar': { value: 0 },
        'humanizer-percent': { textContent: '' },
        'humanizer-progress-status': { textContent: '' },
        'humanizer-submit': { disabled: false, textContent: 'Humanize Text' },
    };
    const payload = events.map((event) => `data: ${JSON.stringify(event)}\r\n\r\n`).join('');
    const bytes = new TextEncoder().encode(payload);
    let offset = 0;
    const context = {
        document: {
            getElementById: (id) => elements[id],
            createElement: () => ({ click: () => { downloads += 1; }, remove() {} }),
            body: { appendChild() {} },
        },
        fetch: async () => ({
            ok: true, status: 200, redirected: false,
            headers: { get: () => 'text/event-stream' },
            body: { getReader: () => ({ read: async () => {
                if (offset >= bytes.length) return { done: true };
                const value = bytes.subarray(offset, offset + splitEvery);
                offset += splitEvery;
                return { value, done: false };
            } }) },
        }),
        FormData: class {},
        Blob, TextDecoder, Uint8Array, URL, atob, crypto: crypto.webcrypto,
        setTimeout: () => {},
        globalThis: null,
    };
    context.globalThis = context;
    context.URL.createObjectURL = () => 'blob:test';
    context.URL.revokeObjectURL = () => {};
    vm.runInNewContext(script, context);
    await submitHandler({ preventDefault() {} });
    return { downloads, status: elements['humanizer-progress-status'].textContent,
             percent: elements['humanizer-percent'].textContent };
}

function fileEvents(content, hash = crypto.createHash('sha256').update(content).digest('hex')) {
    return [
        { type: 'progress', percent: 10, processed: 0, total: 1 },
        { type: 'file-start', filename: 'sample_humanized.docx', size: content.length, sha256: hash },
        { type: 'file-chunk', data: content.toString('base64') },
        { type: 'complete', percent: 100 },
    ];
}

test('CRLF event chunks produce one verified download', async () => {
    const result = await runStream(fileEvents(Buffer.from('complete-word-file')));
    assert.equal(result.downloads, 1);
    assert.equal(result.percent, '100%');
});

test('a mismatched digest blocks the download', async () => {
    const result = await runStream(fileEvents(Buffer.from('tampered-file'), '0'.repeat(64)), 3);
    assert.equal(result.downloads, 0);
    assert.match(result.status, /damaged/);
});

test('a missing file chunk blocks the download', async () => {
    const events = fileEvents(Buffer.from('complete-word-file'));
    events.splice(2, 1);
    const result = await runStream(events);
    assert.equal(result.downloads, 0);
    assert.match(result.status, /incomplete/);
});
