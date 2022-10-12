# https://en.wikipedia.org/wiki/ANSI_escape_code
# https://coolors.co/aa4465-ec7632-dcd5a0-f9cb40-875f00-698c6e-0b3820-5fafff-2f5d9d-7f5e97

# Sets shell environment variables to code for ANSI colors.

# Attributes
export NORMAL='\e[0m'
export BOLD='\e[1m'
export ITALICS='\e[3m'
export UNDERLINE='\e[4m'
export STRIKETHROUGH='\e[9m'

# Foreground colors
export BLACK='\e[30m'
export BROWN='\e[38;2;135;95;0m'        #875F00
export BRIGHT_RED='\e[38;2;175;0;0m'
export LIGHT_RED='\e[38;2;170;68;101m'  #AA4465
export RED='\e[31m'
export DARK_RED='\e[38;5;52m'
export PINK='\e[38;2;231;90;124m'       #E75A7C
export ORANGE='\e[38;2;236;118;50m'     #EC7632
export YELLOW='\e[38;2;249;203;64m'     #F9CB40
export GOLD='\e[38;5;94m'
export GREEN='\e[38;2;105;140;110m'     #698C6E
export DARK_GREEN='\e[38;2;10;51;29m'   #0A331D
export TEAL='\e[38;5;45m'
export CYAN='\e[38;2;95;175;255m'       #5FAFFF
export BLUE='\e[38;2;47;93;157m'        #2F5D9D
export DARK_BLUE='\e[38;5;18m'
export MAGENTA='\e[38;2;170;68;101m'    #AA4465
export DARK_MAGENTA='\e[38;5;63m'
export PURPLE='\e[38;2;127;94;151m'     #7F5E97
export ON_PURPLE='\e[48;2;127;94;151m'  #7F5E97
export DARK_PURPLE='\e[38;5;56m'
export WHITE='\e[37m'
export LIGHT_GRAY='\e[38;2;25;25;25m'
export LGRAY='\e[38;2;25;25;25m'
export GRAY='\e[30m'

# 8-bit: As 256-color lookup tables became common on graphic cards,
# escape sequences were added to select from a pre-defined set of 256
# colors:
#
# ESC[ 38;5;⟨n⟩ m Select foreground color
# ESC[ 48;5;⟨n⟩ m Select background color
#   0-  7:  standard colors (as in ESC [ 30–37 m)
#   8- 15:  high intensity colors (as in ESC [ 90–97 m)
#  16-231:  6 × 6 × 6 cube (216 colors): 16 + 36 × r + 6 × g + b (0 ≤ r, g, b ≤ 5)
# 232-255:  grayscale from black to white in 24 steps
function make_fg_color() {
    if [ $# -ge 3 ]; then
        if [ "$1" -gt "5" ] || [ "$2" -gt "5" ] || [ "$3" -gt "5" ]; then
            echo -ne "\e[38;2;$1;$2;$3m"
        else
            N=$(( 16 + 36 * $1 + 6 * $2 + $3 ))
            echo -ne "\e[38;5;${N}m"
        fi
    elif [ $# -eq 2 ]; then
        N=$(( 16 + 36 * 0 + 6 * $1 + $2 ))
        echo -ne "\e[38;5;${N}m"
    elif [ $# -eq 1 ]; then
        echo -ne "\e[38;5;$1m"
    else
        echo -ne ${LIGHT_GRAY}
    fi
}

function make_bg_color() {
    if [ $# -ge 3 ]; then
        if [ "$1" -gt "5" ] || [ "$2" -gt "5" ] || [ "$3" -gt "5" ]; then
            echo -ne "\e[48;2;$1;$2;$3m"
        else
            N=$(( 16 + 36 * $1 + 6 * $2 + $3 ))
            echo -ne "\e[48;5;${N}m"
        fi
    elif [ $# -eq 2 ]; then
        N=$(( 16 + 36 * 0 + 6 * $1 + $2 ))
        echo -ne "\e[48;5;${N}m"
    elif [ $# -eq 1 ]; then
        echo -ne "\e[48;5;$1m"
    else
        echo -ne ${ON_GRAY}
    fi
}

# Backgrounds
export ON_BLACK='\e[40m'
export ON_LGRAY='\e[48;2;25;25;25m'
export ON_RED='\e[41m'
export ON_ORANGE='\e[48;2;236;118;50m'
export ON_GREEN='\e[48;2;105;140;110m'
export ON_YELLOW='\e[48;2;249;203;64m'
export ON_BLUE='\e[48;2;47;93;157m'
export ON_MAGENTA='\e[48;2;170;68;101m'
export ON_CYAN='\e[48;2;95;175;255m'
export ON_WHITE='\e[47m'
export ON_DARK_PURPLE='\e[48;5;56m'

# Cursor color
export CURSOR='\e[38;5;208m'          # ORANGY
export ON_CURSOR='\e[48;5;208m'

# Reset sequence
export NC="\e[0m"                     # color reset
