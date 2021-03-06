import re
import sys
import operator
from haystack.query import SQ
from django.conf import settings

# Patern_Field_Query = re.compile(r"^(\w+):(\w+)\s*",re.U)
# Patern_Field_Exact_Query = re.compile(r"^(\w+):\"(.+)\"\s*",re.U)
Patern_Field_Query = re.compile(r"^(\w+):",re.U)
Patern_Normal_Query = re.compile(r"^(\w+)\s*",re.U)
Patern_Operator = re.compile(r"^(AND|OR|NOT|\-|\+)\s*",re.U)
Patern_Quoted_Text = re.compile(r"^\"([^\"]*)\"\s*",re.U)

HAYSTACK_DEFAULT_OPERATOR = getattr(settings,'HAYSTACK_DEFAULT_OPERATOR','AND')
DEFAULT_OPERATOR = ''
OP = {
    'AND':operator.and_,
    'OR':operator.or_,
    'NOT':operator.inv,
    '+':operator.and_,
    '-':operator.inv,
}

class NoMatchingBracketsFound(Exception):
    def __init__(self,value=''):
        self.value = value

    def __str__(self):
        return "Matching brackets were not found: "+self.value

class UnhandledException(Exception):
    def __init__(self,value=''):
        self.value = value
    def __str__(self):
        return self.value


def head(string):
    return string.split()[0]

def tail(string):
    return " ".join(string.split()[1:])

class ParseSQ(object):
    def __init__(self, use_default=HAYSTACK_DEFAULT_OPERATOR):
        self.Default_Operator = use_default

    def apply_operand(self,new_sq):
        if self.sq:
            return OP[self.current](self.sq,new_sq)
        return new_sq

    def handle_field_query(self):
        mat = re.search(Patern_Field_Query,self.query)
        search_field = mat.group(1)
        self.query, n = re.subn(Patern_Field_Query,'',self.query,1)
        if re.search(Patern_Quoted_Text,self.query):
            mat = re.search(Patern_Quoted_Text,self.query)
            self.sq = self.apply_operand(SQ(**{search_field+"__exact":mat.group(1)}))
            self.query,n = re.subn(Patern_Quoted_Text,'',self.query,1)
        elif re.search(Patern_Normal_Query,self.query):
            word = head(self.query)
            self.sq = self.apply_operand(SQ(**{search_field:word}))
            self.query = tail(self.query)
        self.current = self.Default_Operator

    def handle_brackets(self):
        no_brackets = 1
        i=1
        assert self.query[0]=="("
        while no_brackets and i<len(self.query):
            if self.query[i]==")":
                no_brackets-=1
            elif self.query[i]=="(":
                no_brackets+=1
            i+=1
        if not no_brackets:
            parser = ParseSQ(self.Default_Operator)
            self.sq = self.apply_operand(parser.parse(self.query[1:i-1]))
        else:
            raise NoMatchingBracketsFound(self.query)
        self.query, self.current = self.query[i:], self.Default_Operator

    def handle_normal_query(self):
        word = head(self.query)
        if self.current == "NOT" or self.current == "-":
            self.current = self.Default_Operator
            self.sq = self.apply_operand(~SQ(content=word))
        else:
            self.sq = self.apply_operand(SQ(content=word))
            self.current = self.Default_Operator
        self.query = tail(self.query)

    def handle_operator_query(self):
        self.current = re.search(Patern_Operator,self.query).group(1)
        self.query,n = re.subn(Patern_Operator,'',self.query,1)
    
    def handle_quoted_query(self):
        mat = re.search(Patern_Quoted_Text,self.query)
        query_temp = mat.group(1)
        #it seams that haystack exact only works if there is a space in the query.So adding a space
        # if not re.search(r'\s',query_temp):
        #     query_temp+=" "
        self.sq = self.apply_operand(SQ(content__exact=query_temp))
        self.query,n = re.subn(Patern_Quoted_Text,'',self.query,1)
        self.current = self.Default_Operator


    def parse(self,query):
        self.query = query
        try:
            self.sq= SQ()
            self.current = self.Default_Operator
            while self.query:
                self.query=self.query.lstrip()
                if re.search(Patern_Field_Query,self.query):
                    self.handle_field_query()
                # elif re.search(Patern_Field_Exact_Query,self.query):
                #     self.handle_field_exact_query()
                elif re.search(Patern_Quoted_Text,self.query):
                    self.handle_quoted_query()
                elif re.search(Patern_Operator,self.query):
                    self.handle_operator_query()
                elif re.search(Patern_Normal_Query,self.query):
                    self.handle_normal_query()
                elif self.query[0]=="(":
                    self.handle_brackets()
                else:
                    self.query=self.query[1:]
        except:
            print  self.sq, self.query, self.current
            raise UnhandledException(sys.exc_info())
        return self.sq

