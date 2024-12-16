#!/bin/bash

if [ $# -eq 1 ]
then
    rm -f 3rdParty/glucose-3.0/core/*.o*
    rm -f 3rdParty/glucose-3.0/core/lib*
    rm -f 3rdParty/glucose-3.0/core/depend.mk
    rm -f 3rdParty/glucose-3.0/utils/*.o*
    rm -rf 3rdParty/kahypar/build
fi

rm -rf build/
rm -f gmon.out
