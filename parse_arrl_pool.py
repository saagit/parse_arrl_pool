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
from typing import List
from typing import Pattern
from typing import Tuple
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

FIRST_QUESTION_RE = re.compile(r'[TGE]1A01 ')
EXTRA_SPACE_RE = re.compile(r'([0-9a-z]-)\s+([a-z])', re.IGNORECASE)
def cleanup_text(text: str) -> str:
    """Returned a cleaned-up version of the passed text

    Any header, errata, etc. from the beginning of text will be removed
    and then Unicode characters (e.g. quotes and dashes) in the text
    are decoded into ASCII.  The result is returned.
    """
    search_index = 0
    while True:
        match_obj = FIRST_QUESTION_RE.search(text[search_index+1:])
        if not match_obj:
            break
        search_index += match_obj.start() + 1
    text = text[search_index:]
    text = unidecode(text)
    text = EXTRA_SPACE_RE.sub(r'\1\2', text)
    return text

WORD_NAMESPACE = ('{http://schemas.openxmlformats.org/'
                  'wordprocessingml/2006/main}')
PARA = WORD_NAMESPACE + 'p'
TEXT = WORD_NAMESPACE + 't'

def get_text_from_docx(filename: str) -> str:
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

def get_text_from_file(filenames: List[str]) -> str:
    """Return the text extracted from the filename passed

    The filename can refer to either a .pdf, .docx or .txt file.
    """
    all_text = ''
    for filename in filenames:
        try:
            file_text = extract_text(filename)
        except PDFSyntaxError:
            pass
        else:
            all_text += cleanup_text(file_text)
            continue

        try:
            file_text = get_text_from_docx(filename)
        except zipfile.BadZipFile:
            pass
        else:
            all_text += cleanup_text(file_text)
            continue

        with open(filename, 'rb') as text_file:
            # Deal with some published files having an extraneous '\xFF'
            file_bytes = text_file.read().replace(b'\xFF', b'')
            file_text = file_bytes.decode()
            all_text += cleanup_text(file_text)
    return all_text

QA_RE = re.compile(r'(?P<QuestionNumber>[TGE][0-9][A-Z][0-9]{2}) ?'
                   r'\((?P<Answer>[A-D])\)'
                   r'(?P<Regulation>\s*?\[[^]]+?\])?\s*?'
                   r'(?P<Question>[^~]+?)\s*?'
                   r'A\. *?(?P<ChoiceA>[^~]+?)\s*?'
                   r'B\. *?(?P<ChoiceB>[^~]+?)\s*?'
                   r'C\. *?(?P<ChoiceC>[^~]+?)\s*?'
                   r'D\. *?(?P<ChoiceD>[^~]+?)\s*?~+')

class Question():
    """A container to hold information about a single question."""
    q_wrapper = textwrap.TextWrapper()
    a_wrapper = textwrap.TextWrapper(initial_indent='   ',
                                     subsequent_indent='      ')
    all_choices_correct_re = re.compile('^All .* correct$')

    def __init__(self, match_obj: re.Match[str]) -> None:
        self.question_number = match_obj.group('QuestionNumber')
        assert len(self.question_number)

        self.answer = match_obj.group('Answer')
        self.regulation = match_obj.group('Regulation')
        self.question = ' '.join(match_obj.group('Question').split())
        self.choices = {}
        self.choices['A'] = ' '.join(match_obj.group('ChoiceA').split())
        self.choices['B'] = ' '.join(match_obj.group('ChoiceB').split())
        self.choices['C'] = ' '.join(match_obj.group('ChoiceC').split())
        self.choices['D'] = ' '.join(match_obj.group('ChoiceD').split())

        assert self.answer
        if not self.regulation or self.regulation.isspace():
            self.regulation = ''
        assert self.question
        for choice in self.choices.values():
            assert choice

    def __str__(self) -> str:
        return (f'{self.question_number} ({self.answer}){self.regulation}\n'
                f'{self.question}\n'
                f'A. {self.choices["A"]}\n'
                f'B. {self.choices["B"]}\n'
                f'C. {self.choices["C"]}\n'
                f'D. {self.choices["D"]}\n'
                f'~~')

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Question):
            return NotImplemented
        return str(self) == str(other)

    def generate_question(self, shuffle_abcd: bool) -> Tuple[str, str]:
        "Returns a string that asks the question."

        # Wrap the text of the question
        question_text = '\n'.join(self.q_wrapper.wrap(self.question))

        if not shuffle_abcd:
            # A is A, B is B, etc.
            choice_lookup = {
                'A': 'A',
                'B': 'B',
                'C': 'C',
                'D': 'D'
            }
        elif self.all_choices_correct_re.match(self.choices['D']):
            # Leave "All choices are correct" as D, but shuffle A, B and C.
            shuffled_choices = random.sample('ABC', 3)
            choice_lookup = {
                'A': shuffled_choices[0],
                'B': shuffled_choices[1],
                'C': shuffled_choices[2],
                'D': 'D'
            }
        else:
            # Shuffle all four choices
            shuffled_choices = random.sample('ABCD', 4)
            choice_lookup = {
                'A': shuffled_choices[0],
                'B': shuffled_choices[1],
                'C': shuffled_choices[2],
                'D': shuffled_choices[3]
            }

        choices = {}
        for original_choice in choice_lookup:
            raw_text = (f'{choice_lookup[original_choice]}. '
                        f'{self.choices[original_choice]}')
            choices[choice_lookup[original_choice]] = (
                '\n'.join(self.a_wrapper.wrap(raw_text)))

        return (choice_lookup[self.answer], (f'{self.question_number}\n'
                                             f'{question_text}\n'
                                             f'{choices["A"]}\n'
                                             f'{choices["B"]}\n'
                                             f'{choices["C"]}\n'
                                             f'{choices["D"]}\n'))

class TwoQuestionsWithSameNumber(Exception):
    """Two different questions with the same number were seen."""

def text_matches_any_re(text: str, regex_list: list[Pattern[str]]) -> bool:
    """Return True iff text matches something in regex_list."""
    for regex in regex_list:
        if regex.match(text):
            return True
    return False

def parse_questions(text: str,
                    include_strs: str,
                    exclude_strs: str) -> dict[str, Question]:
    """Returns a dictionary of Questions extracted from text.

    The dictionary's keys are the question numbers in the order they
    occurred in text.
    """

    if include_strs:
        regex_list = [re.compile(re_str) for re_str in include_strs]
    elif exclude_strs:
        regex_list = [re.compile(re_str) for re_str in exclude_strs]

    questions: dict[str, Question] = {}
    for match_obj in QA_RE.finditer(text):
        key = match_obj.group('QuestionNumber')

        if include_strs:
            if not text_matches_any_re(key, regex_list):
                continue

        elif exclude_strs:
            if text_matches_any_re(key, regex_list):
                continue

        question = Question(match_obj)
        if key in questions and question != questions[key]:
            raise TwoQuestionsWithSameNumber(key)
        questions[key] = question
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

def ask_questions(stdscr: Window,
                  questions: dict[str, Question],
                  shuffle_abcd: bool) -> None:
    """Use curses to test the user.

    Any questions answered correctly will not be output.
    """

    curses.use_default_colors()
    stdscr.clear()

    rows, cols = stdscr.getmaxyx()
    if rows < 24 or cols < 80:
        raise WinTooSmallError

    q_correct = 0
    q_incorrect = 0
    q_skipped = 0
    q_numbers = list(questions.keys())
    q_numbers = random.sample(q_numbers, len(q_numbers))
    for q_number in q_numbers:
        question = questions[q_number]
        stdscr.clear()

        stdscr.addstr(f'       total questions: {len(q_numbers)}\n'
                      f'    correctly answered: {q_correct}\n'
                      f'  incorrectly answered: {q_incorrect}\n'
                      f'               skipped: {q_skipped}\n'
                      f'             remaining: '
                      f'{len(q_numbers) - q_correct - q_incorrect - q_skipped}'
                      f'\n\n')
        correct_answer, question_text = question.generate_question(shuffle_abcd)
        stdscr.addstr(question_text)

        old_pos = stdscr.getyx()
        while True:
            stdscr.addstr('\n[abcdsq?]: ')
            their_answer = stdscr.getkey().upper()
            if their_answer in 'ABCDSQ':
                break
            stdscr.addstr(ASK_QUESTIONS_HELP)
            stdscr.move(*old_pos)

        stdscr.clrtobot()
        stdscr.addch(their_answer)
        if their_answer == 'Q':
            return
        if their_answer == correct_answer:
            q_correct += 1
            del questions[q_number]
        else:
            if their_answer == 'S':
                q_skipped += 1
            else:
                q_incorrect += 1
            stdscr.addstr(f'\nThe correct answer is {correct_answer}.\n'
                          f'Press a key to continue.')
            their_answer = stdscr.getkey()

def main() -> int:
    """The main event."""
    argp = argparse.ArgumentParser()
    # TODO Add --list option to output only the question numbers
    # TODO If -v and -a, output number right/wrong/skipped
    argp.add_argument('-v', '--verbose', action='store_true',
                      help='Print the number of questions to stderr.')
    argp.add_argument('-a', '--ask-questions', action='store_true',
                      help='Correctly answered questions are not output.')
    argp.add_argument('-s', '--shuffle-abcd', action='store_true',
                      help='Implies -a.  The multiple-choices are shuffled.')
    argg = argp.add_mutually_exclusive_group()
    # TODO Add -I and -E options to read included/excluded numbers from file
    # TODO Clarify how -i and -e regexes work (anchored to beginning)?
    argg.add_argument('-i', '--include', action='append', metavar='RE',
                      help='Only include question numbers that match RE.')
    argg.add_argument('-e', '--exclude', action='append', metavar='RE',
                      help='Exclude any question numbers that match RE.')
    argp.add_argument('-o', '--output-file', metavar='FILE',
                      help='Output the questions to text FILE.',
                      type=argparse.FileType('w'), default=sys.stdout)
    argp.add_argument('question_pools', nargs='+', metavar='POOL_FILES',
                      help='.docx, .pdf or .txt containing a question pool')
    args = argp.parse_args()

    text = get_text_from_file(args.question_pools)
    questions = parse_questions(text, args.include, args.exclude)

    if args.shuffle_abcd:
        args.ask_questions = True
    if args.ask_questions:
        try:
            curses.wrapper(ask_questions, questions, args.shuffle_abcd)
        except WinTooSmallError:
            print('The terminal window must be at least 80x24.',
                  file=sys.stderr)
            return 1

    if args.verbose:
        print(f'Outputting {len(questions)} questions.', file=sys.stderr)
    for question_number in questions:
        print(questions[question_number], file=args.output_file)

    return 0

if __name__ == "__main__":
    sys.exit(main())
