"""Minimal KiCad s-expression reader/writer.

Quoted strings are kept as QStr so they round-trip with quotes; bare atoms stay str.
"""
import re


class QStr(str):
    pass


_tok = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+', re.S)


def _unescape(s):
    return re.sub(r'\\(.)', lambda m: {'n': '\n', 't': '\t'}.get(m.group(1), m.group(1)), s)


def parse(text):
    stack, cur = [], []
    for m in _tok.finditer(text):
        t = m.group(0)
        if t == '(':
            stack.append(cur)
            cur = []
        elif t == ')':
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif t[0] == '"':
            cur.append(QStr(_unescape(t[1:-1])))
        else:
            cur.append(t)
    assert not stack
    return cur[0]


def load(path):
    with open(path, encoding='utf-8') as f:
        return parse(f.read())


def _q(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def dumps(node, indent=0):
    if not isinstance(node, list):
        if isinstance(node, QStr):
            return _q(node)
        if isinstance(node, float):
            return fmt(node)
        return str(node)
    simple = all(not isinstance(x, list) for x in node)
    if simple:
        return '(' + ' '.join(dumps(x) for x in node) + ')'
    pad = '\t' * (indent + 1)
    parts = ['(' + dumps(node[0])]
    line_items = []
    for x in node[1:]:
        if isinstance(x, list):
            parts.append('\n' + pad + dumps(x, indent + 1))
        else:
            parts.append(' ' + dumps(x))
    return ''.join(parts) + '\n' + '\t' * indent + ')'


def fmt(v):
    s = f'{v:.6f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def find(node, head):
    return [x for x in node if isinstance(x, list) and x and x[0] == head]


def first(node, head, default=None):
    for x in node:
        if isinstance(x, list) and x and x[0] == head:
            return x
    return default


def val(node, head, idx=1, default=None):
    f = first(node, head)
    return f[idx] if f is not None and len(f) > idx else default
