const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const script = fs.readFileSync('static/js/ppt.js', 'utf8');

async function run(response) {
    let handler;
    let downloads = 0;
    const button = { disabled: false };
    const status = { hidden: true, textContent: '' };
    const error = { hidden: true, textContent: '' };
    const form = {
        action: '/ppt/download',
        reportValidity: () => true,
        querySelector: () => button,
        addEventListener: (_event, callback) => { handler = callback; },
    };
    const context = {
        document: {
            getElementById: (id) => ({
                'ppt-download-form': form,
                'ppt-download-status': status,
                'ppt-download-error': error,
            })[id],
            createElement: () => ({ click: () => { downloads += 1; }, remove() {} }),
            body: { appendChild() {} },
        },
        fetch: async () => response,
        FormData: class {},
        URL,
        setTimeout: () => {},
        window: { location: { assign() {} } },
    };
    context.URL.createObjectURL = () => 'blob:pptx';
    context.URL.revokeObjectURL = () => {};
    vm.runInNewContext(script, context);
    await handler({ preventDefault() {} });
    return { downloads, status, error, button };
}

test('successful PowerPoint request downloads and re-enables form', async () => {
    const result = await run({
        ok: true, redirected: false,
        headers: { get: (name) => ({
            'Content-Type': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'Content-Disposition': 'attachment; filename="water-cycle.pptx"',
        })[name] },
        blob: async () => new Blob(['pptx']),
    });
    assert.equal(result.downloads, 1);
    assert.match(result.status.textContent, /download is starting/);
    assert.equal(result.button.disabled, false);
});

test('AI error is shown without a download', async () => {
    const result = await run({
        ok: false, redirected: false,
        headers: { get: () => 'application/json' },
        json: async () => ({ error: 'AI is busy. Please try again later.' }),
    });
    assert.equal(result.downloads, 0);
    assert.equal(result.error.hidden, false);
    assert.match(result.error.textContent, /AI is busy/);
    assert.equal(result.button.disabled, false);
});
