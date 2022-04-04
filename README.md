# parse_arrl_pool
parse_arrl_pool.py is a Python script that is able to parse .docx,
.pdf or .txt files that contain amateur radio examination question
pools from [NCVEC](http://www.ncvec.org/) or
[ARRL](http://www.arrl.org/question-pools).  It internally creates a
dictionary of question objects that contain the information parsed
from the file(s).  It outputs the question objects to stdout or an
output file as ASCII text in the same format as the .txt files from
NCVEC.

Questions can be included or excluded by specifying regular
expressions that are matched against the question numbers.

There is also an option to uses curses to quiz the user on the
questions and any question that is answered incorrectly or skipped
will be output.  Shuffling the multiple choice answers is an option
for this option.  Note that parse_arrl_pool.py does nothing to present
the figures that are required by some questions so ensure that you
have those available in another way.

A benefit of producing output in a format that can also be input is
that it is trivial to produce subsets of the question pools by either
filtering the question numbers by regular expression or by using the
quiz to filter out questions where the answers are well known.

Note that the .docx files from [NCVEC](http://www.ncvec.org) appear to
be the most authoritative, but if you are interested in comparing the
various files available, parse_arrl_pool.py makes it easy to produce a
.txt file version of each and then use simple comparison tools to
compare the .txt files.

```
usage: parse_arrl_pool.py [-h] [-v] [-a] [-s] [-I RE | -E RE] [-o FILE]
                          POOL_FILES [POOL_FILES ...]

positional arguments:
  POOL_FILES            .docx, .pdf or .txt containing a question pool

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Print the number of questions to stderr.
  -a, --ask-questions   Correctly answered questions are not output.
  -s, --shuffle-abcd    Implies -a. The multiple-choices are shuffled.
  -I RE, --include RE   Only include question numbers that match RE.
  -E RE, --exclude RE   Exclude any question numbers that match RE.
  -o FILE, --output-file FILE
                        Output the questions to text FILE.
```
