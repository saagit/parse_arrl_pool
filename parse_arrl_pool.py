#!/usr/bin/env python3

"""Parses an ARRL question pool."""

# Copyright 2022 Scott A. Anderson
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Commands to do static checks:
# mypy --strict parse_arrl_pool.py mypy_stubs
# pylint parse_arrl_pool.py

import argparse
import curses
import random
import re
import sys
import textwrap
from typing import TYPE_CHECKING
from xml.etree.cElementTree import XML
import zipfile

from pdfminer.high_level import extract_text
from pdfminer.pdfparser import PDFSyntaxError
from unidecode import unidecode

if TYPE_CHECKING:
    from _curses import _CursesWindow # pylint: disable=no-name-in-module
    Window = _CursesWindow
else:
    from typing import Any # pylint: disable=ungrouped-imports
    Window = Any

WORD_NAMESPACE = ('{http://schemas.openxmlformats.org/'
                  'wordprocessingml/2006/main}')
PARA = WORD_NAMESPACE + 'p'
TEXT = WORD_NAMESPACE + 't'

def get_txt_from_docx(filename: str) -> str:
    """Return the text extracted from the passed .docx filename"""
    document = zipfile.ZipFile(filename)
    xml_content = document.read('word/document.xml')
    document.close()
    tree = XML(xml_content)

    paragraphs = []
    for paragraph in tree.iter(PARA):
        texts = [node.text
                 for node in paragraph.iter(TEXT)
                 if node.text]
        if texts:
            paragraphs.append(''.join(texts))

    return '\n\n'.join(paragraphs)

def get_txt_from_file(filename: str) -> str:
    """Return the text extracted from the filename passed

    The filename can refer to either a .pdf, .docx or .txt file.
    """
    try:
        return extract_text(filename)
    except PDFSyntaxError:
        pass

    try:
        return get_txt_from_docx(filename)
    except zipfile.BadZipFile:
        pass

    with open(filename) as txt_file:
        return txt_file.read()

def cleanup_txt(txt: str) -> str:
    """Returned a cleaned-up version of the passed txt

    Any header, errata, etc. from the beginning of txt will be removed
    and then Unicode characters (e.g. quotes and dashes) in the txt
    are decoded into ASCII.  The result is returned.
    """
    to_skip = txt.find('SUBELEMENT')
    if to_skip > 0:
        txt = txt[to_skip:]
    return unidecode(txt)

QA_RE = re.compile(r'(?P<QuestionNumber>[TGE][0-9][A-Z][0-9]{2}) ?'
                   r'\((?P<Answer>[A-D])\)'
                   r'(?P<Regulation>\s*?\[[^]]+?\])?\s*?'
                   r'(?P<Question>[^~]+?)\s*?'
                   r'A\. *?(?P<OptionA>[^~]+?)\s*?'
                   r'B\. *?(?P<OptionB>[^~]+?)\s*?'
                   r'C\. *?(?P<OptionC>[^~]+?)\s*?'
                   r'D\. *?(?P<OptionD>[^~]+?)\s*?~+')

class Question():
    """A container to hold information about a single question."""
    # pylint: disable=too-many-instance-attributes
    def __init__(self, match_obj: re.Match[str]) -> None:
        self.question_number = match_obj.group('QuestionNumber')
        assert len(self.question_number)

        self.answer = match_obj.group('Answer')
        self.regulation = match_obj.group('Regulation')
        self.question = ' '.join(match_obj.group('Question').split())
        self.option_a = ' '.join(match_obj.group('OptionA').split())
        self.option_b = ' '.join(match_obj.group('OptionB').split())
        self.option_c = ' '.join(match_obj.group('OptionC').split())
        self.option_d = ' '.join(match_obj.group('OptionD').split())

        assert self.answer
        if not self.regulation or self.regulation.isspace():
            self.regulation = ''
        assert self.question
        assert self.option_a
        assert self.option_b
        assert self.option_c
        assert self.option_d

        self.q_wrapper = textwrap.TextWrapper()
        self.a_wrapper = textwrap.TextWrapper(initial_indent='   ',
                                              subsequent_indent='      ')

    def __str__(self) -> str:
        return (f'{self.question_number} ({self.answer}){self.regulation}\n'
                f'{self.question}\n'
                f'A. {self.option_a}\n'
                f'B. {self.option_b}\n'
                f'C. {self.option_c}\n'
                f'D. {self.option_d}\n'
                f'~~')

    def question_to_ask(self) -> str:
        "Returns a string that asks the question."
        q_txt = '\n'.join(self.q_wrapper.wrap(self.question))

        opt_a_txt = '\n'.join(self.a_wrapper.wrap(f'A. {self.option_a}'))
        opt_b_txt = '\n'.join(self.a_wrapper.wrap(f'B. {self.option_b}'))
        opt_c_txt = '\n'.join(self.a_wrapper.wrap(f'C. {self.option_c}'))
        opt_d_txt = '\n'.join(self.a_wrapper.wrap(f'D. {self.option_d}'))
        return (f'{self.question_number}\n'
                f'{q_txt}\n'
                f'{opt_a_txt}\n'
                f'{opt_b_txt}\n'
                f'{opt_c_txt}\n'
                f'{opt_d_txt}\n')

def parse_questions(txt: str) -> dict[str, Question]:
    """Returns a dictionary of Questions extracted from txt.

    The dictionary's keys are the question numbers in the order they
    occurred in txt.
    """
    questions = {}
    for match in QA_RE.finditer(txt):
        key = match.group('QuestionNumber')
        questions[key] = Question(match)
    return questions

ASK_QUESTIONS_HELP = (
    '\n' +
    '\n'.join(textwrap.wrap('Press the letter of your answer '
                            '("a", "b", "c" or "d").  If your answer is '
                            'correct, the question will not be output. '
                            'You may press "s" to skip answering a question. '
                            'If you wish to quit, press "q" in which case '
                            'all incorrectly answered and unanswered '
                            'questions will be immediately output.')) +
    '\n')

class WinTooSmallError(Exception):
    """Signal that the terminal window is too small."""
    pass

def ask_questions(stdscr: Window, questions: dict[str, Question]) -> None:
    """Use curses to test the user.

    Any questions answered correctly will not be output.
    """

    curses.use_default_colors()
    stdscr.clear()

    rows, cols = stdscr.getmaxyx()
    if rows < 24 or cols < 80:
        raise WinTooSmallError

    # TODO shuffle answer options
    qnums = list(questions.keys())
    q_num = len(qnums)
    q_right = 0
    q_wrong = 0
    q_skipped = 0
    random.shuffle(qnums)
    for key in qnums:
        qobj = questions[key]
        stdscr.clear()

        stdscr.addstr(f'       total questions: {q_num}\n')
        stdscr.addstr(f'    correctly answered: {q_right}\n')
        stdscr.addstr(f'  incorrectly answered: {q_wrong}\n')
        stdscr.addstr(f'               skipped: {q_skipped}\n')
        stdscr.addstr(f'             remaining: '
                      f'{q_num - q_right - q_wrong - q_skipped}\n\n')
        stdscr.addstr(qobj.question_to_ask())

        pos_y, pos_x = stdscr.getyx()
        while True:
            stdscr.addstr('\n[abcdsq?]: ')
            ans = stdscr.getkey().upper()
            if ans in 'ABCDSQ':
                break
            stdscr.addstr(ASK_QUESTIONS_HELP)
            stdscr.move(pos_y, pos_x)

        stdscr.clrtobot()
        stdscr.addch(ans)
        if ans == 'Q':
            return
        if ans == qobj.answer:
            q_right += 1
            del questions[key]
        else:
            if ans == 'S':
                q_skipped += 1
            else:
                q_wrong += 1
            stdscr.addstr(f'\nThe correct answer is {qobj.answer}.\n')
            stdscr.addstr('Press a key to continue.')
            ans = stdscr.getkey()

def main() -> int:
    """The main event."""
    argp = argparse.ArgumentParser()
    argp.add_argument('-a', '--ask-questions', action='store_true')
    argp.add_argument('-o', '--output-file',
                      type=argparse.FileType('w'), default=sys.stdout)
    argp.add_argument('-v', '--verbose', action='store_true')
    argp.add_argument('pool_pdf_or_docx_or_txt')
    args = argp.parse_args()

    txt = cleanup_txt(get_txt_from_file(args.pool_pdf_or_docx_or_txt))
    questions = parse_questions(txt)

    if args.ask_questions:
        try:
            curses.wrapper(ask_questions, questions)
        except WinTooSmallError:
            print(f'The terminal window must be at least 80x24.',
                  file=sys.stderr)
            return 1

    if args.verbose:
        print(f'Outputting {len(questions)} questions.', file=sys.stderr)
    for key in questions:
        print(questions[key], file=args.output_file)

    return 0

if __name__ == "__main__":
    sys.exit(main())
