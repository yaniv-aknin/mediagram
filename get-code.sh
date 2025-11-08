#!/bin/bash

[ -d code ] && { echo "code/ already exists" ; exit 1; }

set -e

mkdir code
cd code

git clone git@github.com:python-telegram-bot/python-telegram-bot.git
git clone git@github.com:simonw/llm.git
git clone git@github.com:simonw/llm-anthropic.git
git clone git@github.com:lepture/mistune.git
