 # ############################################################################
 #
 # Copyright (c) Microsoft Corporation. 
 #
 # This source code is subject to terms and conditions of the Apache License, Version 2.0. A 
 # copy of the license can be found in the License.html file at the root of this distribution. If 
 # you cannot locate the Apache License, Version 2.0, please send an email to 
 # vspython@microsoft.com. By using this source code in any fashion, you are agreeing to be bound 
 # by the terms of the Apache License, Version 2.0.
 #
 # You must not remove this notice, or any other, from this software.
 #
 # ###########################################################################

import re
import sys
import types
import PythonScraper
try:
    import thread
except:
    import _thread as thread

def builtins_keys():
    if isinstance(__builtins__, dict):
        return __builtins__.keys()
    return dir(__builtins__)

def get_builtin(name):
    if isinstance(__builtins__, dict):
        return __builtins__[name]

    return getattr(__builtins__, name)

BUILTIN_TYPES = [type_name for type_name in builtins_keys() if type(get_builtin(type_name)) is type]
if sys.version >= '3.':
    BUILTIN = 'builtins'
else:
    BUILTIN = '__builtin__'

TYPE_OVERRIDES = {'string': PythonScraper.type_to_name(types.CodeType),
                  's': PythonScraper.type_to_name(str),
                  'integer': PythonScraper.type_to_name(int),
                  'boolean': PythonScraper.type_to_name(bool),
                  'number': PythonScraper.type_to_name(int),
                  'pid': PythonScraper.type_to_name(int),
                  'ppid': PythonScraper.type_to_name(int),
                  'fd': PythonScraper.type_to_name(int),
                  'handle': PythonScraper.type_to_name(int),
                  'Exit': PythonScraper.type_to_name(int),
                  'fd2': PythonScraper.type_to_name(int),
                  'Integral': PythonScraper.type_to_name(int),
                  'exit_status':PythonScraper.type_to_name(int),
                  'old_mask': PythonScraper.type_to_name(int),
                  'source': PythonScraper.type_to_name(str),
                  'newpos': PythonScraper.type_to_name(int),
                  'key': PythonScraper.type_to_name(str),
                  'dictionary': PythonScraper.type_to_name(dict),
                  'None': PythonScraper.type_to_name(type(None)),
                  'floating': PythonScraper.type_to_name(float),
                  'filename': PythonScraper.type_to_name(str),
                  'path': PythonScraper.type_to_name(str),
                  'byteswritten': PythonScraper.type_to_name(int),
                  'Unicode': PythonScraper.type_to_name(float),
                  'True':  PythonScraper.type_to_name(bool),
                  'False':  PythonScraper.type_to_name(bool),
                  'lock': PythonScraper.type_to_name(thread.LockType),
                  'code': PythonScraper.type_to_name(types.CodeType),
                  'module': PythonScraper.type_to_name(types.ModuleType),
                  'size': PythonScraper.type_to_name(int),
                  'INT': PythonScraper.type_to_name(int),
                  'STRING': PythonScraper.type_to_name(str),
                  'TUPLE': PythonScraper.type_to_name(tuple),
                  'OBJECT': PythonScraper.type_to_name(object),
                  'LIST': PythonScraper.type_to_name(list),
                  'DICT': PythonScraper.type_to_name(dict),
                }

RETURN_TYPE_OVERRIDES = dict(TYPE_OVERRIDES)
RETURN_TYPE_OVERRIDES.update({'string': PythonScraper.type_to_name(str)})

def type_name_to_type(name, mod, type_overrides = TYPE_OVERRIDES):
    arg_type = type_overrides.get(name, None)
    if arg_type is None:
        if name in BUILTIN_TYPES:
            arg_type = PythonScraper.type_to_name(get_builtin(name))
        elif mod is not None and name in mod.__dict__:
            arg_type = PythonScraper.memoize_type_name((mod.__name__, name))
        elif name.startswith('list'):
            arg_type = PythonScraper.type_to_name(list)
        elif name == 'unicode':
            # Py3k, some doc strings still have unicode in them.
            arg_type = PythonScraper.type_to_name(str)
        else:
            # see if we can find it in any module we've imported...
            for mod_name, mod in sys.modules.items():
                if mod is not None and name in mod.__dict__ and isinstance(mod.__dict__[name], type):
                    arg_type = (mod_name, name)
                    break
            else:
                first_space = name.find(' ')
                if first_space != -1:
                    return type_name_to_type(name[:first_space], mod, type_overrides)
                arg_type = ('', name)
    return arg_type

OBJECT_TYPE = PythonScraper.type_to_name(object)

TOKENS_REGEX = (
    '('
    '(?:[a-zA-Z_][0-9a-zA-Z_-]*)|'  # identifier
    '(?:[0-9]+[lL]?)|'              # integer value
    '(?:[0-9]*\.[0-9]+)|'           # floating point value
    '(?:\.\.\.)|'                   # ellipsis
    '(?:\.)|'                      # dot
    '(?:\()|'                      # open paren
    '(?:\))|'                      # close paren
    '(?:\:)|'                      # colon
    '(?:-->)|'                      # return value
    '(?:->)|'                      # return value
    '(?:=>)|'                      # return value
    '(?:[,])|'                      # comma
    '(?:=)|'                      # assignment (default value)
    '(?:\.\.\.)|'                      # ellipsis
    '(?:\[)|'
    '(?:\])|'
    '(?:\*\*)|'
    '(?:\*)|'
     ')'
    )

def get_ret_type(ret_type, obj_class, mod):
    if ret_type is not None:
        if ret_type == 'copy' and obj_class is not None:
            # returns a copy of self
            return PythonScraper.type_to_name(obj_class)
        else:
            return type_name_to_type(ret_type, mod, RETURN_TYPE_OVERRIDES)


def parse_doc_str(input_str, module_name, mod, func_name, extra_args = [], obj_class = None):    
    # we split, so as long as we have all tokens every other item is a token, and the
    # rest are empty space.  If we have unrecognized tokens (for example during the description
    # of the function) those will show up in the even locations.  We do join's and bring the
    # entire range together in that case.
    tokens = re.split(TOKENS_REGEX, input_str) 
    start_token = 0
    last_identifier = None
    cur_token = 1
    overloads = []
    while cur_token < len(tokens):
        token = tokens[cur_token]
        # see if we have modname.funcname(
        if (cur_token + 10 < len(tokens) and
            token == module_name and 
            tokens[cur_token + 2] == '.' and
            tokens[cur_token + 4] == func_name and
            tokens[cur_token + 6] == '('):
            sig_start = cur_token
            args, ret_type, cur_token = parse_args(tokens, cur_token + 10, mod)

            if not args and overloads:
                # if we already parsed an overload, and are now getting an argless
                # overload we're likely just seeing a reference to the function in
                # a doc string, let's ignore that.  This is betting on the idea that
                # people list overloads first, then doc strings, and that people tend
                # to list overloads from simplest to more complex. an example of this
                # is the future_builtins.ascii doc string
                continue

            doc_str = ''.join(tokens[start_token:sig_start])
            if doc_str.find(' ') == -1:
                doc_str = ''
            start_token = cur_token
            overload = {'args': extra_args + args, 'doc': doc_str}
            ret_tuple = get_ret_type(ret_type, obj_class, mod)
            if ret_tuple is not None:
                overload['ret_type'] = ret_tuple
            overloads.append(overload)
        # see if we have funcname(
        elif (cur_token + 4 < len(tokens) and
              token == func_name and
              tokens[cur_token + 2] == '('):
            sig_start = cur_token
            args, ret_type, cur_token = parse_args(tokens, cur_token + 4, mod)

            if not args and overloads:
                # if we already parsed an overload, and are now getting an argless
                # overload we're likely just seeing a reference to the function in
                # a doc string, let's ignore that.  This is betting on the idea that
                # people list overloads first, then doc strings, and that people tend
                # to list overloads from simplest to more complex. an example of this
                # is the future_builtins.ascii doc string
                continue
            
            doc_str = ''.join(tokens[start_token:sig_start])
            if doc_str.find(' ') == -1:
                doc_str = ''
            start_token = cur_token
            overload = {'args': extra_args + args, 'doc': doc_str}
            ret_tuple = get_ret_type(ret_type, obj_class, mod)
            if ret_tuple is not None:
                overload['ret_type'] = ret_tuple
            overloads.append(overload)

        else:
            # append to doc string
            cur_token += 2

    finish_doc = ''.join(tokens[start_token:cur_token])
    if finish_doc:
        for overload in overloads:
            overload['doc'] += finish_doc            
    return overloads


IDENTIFIER_REGEX = re.compile('^[a-zA-Z_][a-zA-Z_0-9-]*$')

def is_identifier(token):
    if IDENTIFIER_REGEX.match(token):
        return True
    return False

RETURN_TOKENS = set(['-->', '->', '=>', 'return'])

def parse_args(tokens, cur_token, module):
    args = []
    star_args = None
    is_optional = False
    default_value = None
    annotation = None
    ret_type = None
    while cur_token < len(tokens):
        token = tokens[cur_token]
        if token == '[':
            # optional arg
            is_optional = True
        elif token == '*':
            star_args = '*'
        elif token == '**':
            star_args = '**'
        elif token == ')':
            cur_token += 2
            break
        elif token == ',':
            cur_token += 2
            continue
        else:
            arg_name = token
            if cur_token + 2 < len(tokens) and is_identifier(tokens[cur_token + 2]):
                # C cstyle sig, 'int foo'
                arg_name = tokens[cur_token + 2]
                annotation = token
                cur_token += 2

            if cur_token + 4 < len(tokens) and tokens[cur_token + 2] == '=':
                default_value = tokens[cur_token + 4]
                cur_token += 4
            if cur_token + 4 < len(tokens) and tokens[cur_token + 2] == ':':
                annotation = tokens[cur_token + 4]
                cur_token += 4

            arg = {'name': arg_name}
            if default_value is not None:
                arg['default_value'] = default_value
            elif is_optional:
                arg['default_value'] = 'None'

            if annotation is not None:
                arg['type'] = type_name_to_type(annotation, module)
            if star_args is not None:
                arg['arg_format'] = star_args
            elif token == '...':
                arg['arg_format'] = '*'
            
            while cur_token + 2 < len(tokens) and tokens[cur_token + 2] == ']':
                cur_token += 2
    
            args.append(arg)
            
            is_optional = False
            star_args = None
            default_value = None

        cur_token += 2

    # end of params, check for ret value
    if cur_token + 2 < len(tokens) and tokens[cur_token] in RETURN_TOKENS:
        ret_type_start = cur_token + 2
        # we might have a descriptive return value, 'list of foo'
        while ret_type_start < len(tokens) and is_identifier(tokens[ret_type_start]):
            if tokens[ret_type_start - 1].find('\n') != -1:
                break
            ret_type_start += 2

        ret_type = ''.join(tokens[cur_token + 2:ret_type_start]).strip()
        cur_token = ret_type_start
    elif (cur_token + 4 < len(tokens) and 
        tokens[cur_token] == ':' and tokens[cur_token + 2] in RETURN_TOKENS):
        ret_type_start = cur_token + 4
        # we might have a descriptive return value, 'list of foo'
        while ret_type_start < len(tokens) and is_identifier(tokens[ret_type_start]):
            if tokens[ret_type_start - 1].find('\n') != -1:
                break
            ret_type_start += 2

        ret_type = ''.join(tokens[cur_token + 4:ret_type_start]).strip()
        cur_token = ret_type_start

    return args, ret_type, cur_token


def get_overloads_from_doc_string(doc_str, mod, obj_class, func_name, extra_args = []):
    if isinstance(doc_str, (str, unicode)):
        decl_mod = None
        if mod is not None:
            decl_mod = sys.modules.get(mod, None)

        res = parse_doc_str(doc_str, mod, decl_mod, func_name, extra_args, obj_class)
        if res:
            return tuple(res)
    return None


def get_overloads(func, is_method = False):
    if is_method:
        extra_args = [{'type': PythonScraper.type_to_name(object), 'name': 'self'}]
    else:
        extra_args = []

    return get_overloads_from_doc_string(func.__doc__, 
                                         getattr(func, '__module__', None), 
                                         getattr(func, '__objclass__', None),
                                         getattr(func, '__name__', None),
                                         extra_args)

def get_descriptor_type(descriptor):
	return object

def get_new_overloads(type_obj, obj):
    res = get_overloads_from_doc_string(type_obj.__doc__, 
                                        getattr(type_obj, '__module__', None), 
                                        type(type_obj), 
                                        getattr(type_obj, '__name__', None),
                                        [{'type': PythonScraper.type_to_name(type), 'name': 'cls'}])

    if not res:
        res = get_overloads_from_doc_string(obj.__doc__, 
                                            getattr(type_obj, '__module__', None), 
                                            type(type_obj), 
                                            getattr(type_obj, '__name__', None))
    return res


if __name__ == '__main__':
    r = parse_doc_str('reduce(function, sequence[, initial]) -> value', '__builtin__', sys.modules['__builtin__'], 'reduce')
    assert r == [
           {'args': [
                {'name': 'function'},
                {'name': 'sequence'},
                {'default_value': 'None', 'name': 'initial'}], 
            'doc': '', 
            'ret_type': ('', 'value')
           }
        ]

    r = parse_doc_str('pygame.draw.arc(Surface, color, Rect, start_angle, stop_angle, width=1): return Rect', 
                         'draw',
                         None,
                         'arc')
    import pprint
    assert r == [
           {'args': [
               {'name': 'color'},
               {'name': 'Rect'},
               {'name': 'start_angle'},
               {'name': 'stop_angle'},
               {'default_value': '1', 'name': 'width'}],
            'doc': '',
            'ret_type': ('', 'Rect')
           }
    ]

    r = parse_doc_str('''B.isdigit() -> bool

Return True if all characters in B are digits
and there is at least one character in B, False otherwise.''',
                    'bytes',
                    None,
                    'isdigit')

    assert r == [
        {'args': [],
         'doc': 'Return True if all characters in B are digits\nand there is at least one character in B, False otherwise.',
         'ret_type': ('__builtin__', 'bool')}
    ]
    r = parse_doc_str('x.__init__(...) initializes x; see help(type(x)) for signature',
                      'str',
                      None,
                      '__init__')

    assert r == [{'args': [{'arg_format': '*', 'name': '...'}],
                  'doc': 'initializes x; see help(type(x)) for signature'}]

    r = parse_doc_str('S.find(sub [,start [,end]]) -> int',
                         'str',
                         None,
                         'find')

    assert r == [{'args': [{'name': 'sub'},
                 {'default_value': 'None', 'name': 'start'},
                 {'default_value': 'None', 'name': 'end'}],
                  'doc': '',
                  'ret_type': ('__builtin__', 'int')}]

    r = parse_doc_str('S.format(*args, **kwargs) -> unicode',
                      'str',
                      None,
                      'format')
    assert r == [
                 {'args': [
                           {'arg_format': '*', 'name': 'args'},
                           {'arg_format': '**', 'name': 'kwargs'}
                          ],
                 'doc': '',
                 'ret_type': ('__builtin__', 'unicode')}
    ]
    
    r = parse_doc_str("'ascii(object) -> string\n\nReturn the same as repr().  In Python 3.x, the repr() result will\\ncontain printable characters unescaped, while the ascii() result\\nwill have such characters backslash-escaped.'",
            'future_builtins',
            None,
            'ascii')
    assert r == [{'args': [{'name': 'object'}],
                 'doc': "Return the same as repr().  In Python 3.x, the repr() result will\\ncontain printable characters unescaped, while the ascii() result\\nwill have such characters backslash-escaped.'",
                 'ret_type': ('__builtin__', 'str')}
    ]

    r = parse_doc_str('f(INT class_code) => SpaceID',
                'foo',
                None,
                'f')    
    assert r == [{'args': [{'name': 'class_code', 'type': ('__builtin__', 'int')}],
        'doc': '',
        'ret_type': ('', 'SpaceID')}]

    r = parse_doc_str('compress(data, selectors) --> iterator over selected data\n\nReturn data elements',
                      'itertools',
                      None,
                      'compress')
    assert r == [{'args': [{'name': 'data'}, {'name': 'selectors'}],
                  'doc': 'Return data elements',
                  'ret_type': ('', 'iterator')}]
    