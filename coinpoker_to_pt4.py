#!/usr/bin/env python3
"""Convert CoinPoker cash game hand histories (NLH) to PokerStars format for PokerTracker 4."""
import re
import sys
from pathlib import Path


def fmt(v):
    return f"{v:.2f}"


def convert_hand(hand):
    lines = [l for l in hand.strip().split('\n') if l.strip()]
    if not lines:
        return ''

    header = lines[0]
    hm = re.match(
        r'Hand #(\d+): NLH \(₮([\d.]+)/₮([\d.]+)\) '
        r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) \w+',
        header
    )
    if not hm:
        return ''

    hand_id, sb_str, bb_str, dt = hm.group(1), hm.group(2), hm.group(3), hm.group(4)
    bb_amt = float(bb_str)

    straddle_posts = []
    for l in lines:
        sm = re.match(r'(\S+): STRADDLE ₮([\d.]+)', l.strip())
        if sm:
            straddle_posts.append((sm.group(1), sm.group(2)))

    player_invested = {}
    current_facing_bet = bb_amt
    last_aggressive = None
    splash_amount = 0.0
    in_second_board = False
    hole_cards_done = False

    for _, amt_str in straddle_posts:
        amt = float(amt_str)
        if amt > current_facing_bet:
            current_facing_bet = amt

    out = [
        "PokerStars Hand #%s:  Hold'em No Limit ($%s/$%s) - %s ET"
        % (hand_id, sb_str, bb_str, dt)
    ]

    pending_call = None

    def flush_pending():
        nonlocal pending_call
        if pending_call:
            out.append(pending_call[1])
            pending_call = None

    def reset_street():
        nonlocal current_facing_bet, last_aggressive
        player_invested.clear()
        current_facing_bet = 0.0
        last_aggressive = None

    for raw in lines[1:]:
        line = raw.strip()
        if not line:
            continue

        if line.startswith('Game ended:'):
            flush_pending(); continue
        if line in ('Hand was run once', 'Hand was run two times', 'Hand was run three times'):
            flush_pending(); continue
        if re.match(r'Board \[\s*\]', line):
            flush_pending(); continue
        if re.match(r'Dealt to \S+$', line):
            continue

        if re.match(r'SPLASH dropped ₮', line):
            splash_amount += float(re.match(r'SPLASH dropped ₮([\d.]+)', line).group(1))
            flush_pending(); continue

        if re.match(r'\S+: STRADDLE ₮', line):
            continue

        line = line.replace('₮', '$')

        if re.match(r'\*\*\* SECOND (FLOP|TURN|RIVER) \*\*\*', line):
            flush_pending(); in_second_board = True; continue
        if re.match(r'\*\*\* SECOND SHOWDOWN \*\*\*', line):
            flush_pending(); in_second_board = True; continue
        if re.match(r'\*\*\* FIRST SHOWDOWN \*\*\*', line):
            flush_pending(); in_second_board = False
            out.append('*** SHOWDOWN ***'); continue
        if re.match(r'\*\*\* SUMMARY \*\*\*', line):
            flush_pending(); in_second_board = False
            out.append('*** SUMMARY ***'); continue

        line = re.sub(r'\*\*\* FIRST (FLOP|TURN|RIVER) \*\*\*', r'*** \1 ***', line)
        if line.startswith('SECOND Board'):
            continue
        line = re.sub(r'^FIRST Board', 'Board', line)
        if in_second_board:
            continue

        if re.match(r'\*\*\* HOLE CARDS \*\*\*', line):
            flush_pending()
            if not hole_cards_done:
                for player, amt_str in straddle_posts:
                    amt = float(amt_str)
                    player_invested[player] = amt
                    out.append(f'{player}: posts big blind ${fmt(amt)}')
                hole_cards_done = True
            out.append(line)
            continue

        street_m = re.match(r'\*\*\* (FLOP|TURN|RIVER|SHOWDOWN|SUMMARY) \*\*\*', line)
        if street_m:
            flush_pending()
            if street_m.group(1) in ('FLOP', 'TURN', 'RIVER'):
                reset_street()
            out.append(line); continue

        posts_m = re.match(r'(\S+): posts (small|big) blind \$([\d.]+)', line)
        if posts_m:
            flush_pending()
            player, btype, amt = posts_m.group(1), posts_m.group(2), float(posts_m.group(3))
            player_invested[player] = amt
            if btype == 'big' and amt > current_facing_bet:
                current_facing_bet = amt
            out.append(line); continue

        ret_m = re.match(r'(\S+): RETURN \$([\d.]+)', line)
        if ret_m:
            flush_pending()
            out.append('Uncalled bet ($%s) returned to %s' % (ret_m.group(2), ret_m.group(1)))
            continue

        allin_m = re.match(r'(\S+): ALLIN \$([\d.]+)', line)
        if allin_m:
            flush_pending()
            player     = allin_m.group(1)
            additional = float(allin_m.group(2))
            prev       = player_invested.get(player, 0.0)
            total      = round(prev + additional, 2)
            player_invested[player] = total

            if last_aggressive in ('raise', 'bet'):
                if total > current_facing_bet:
                    converted = '%s: raises $%s to $%s and is all-in' % (
                        player, fmt(round(total - current_facing_bet, 2)), fmt(total))
                    current_facing_bet = total
                    last_aggressive = 'raise'
                else:
                    converted = '%s: calls $%s and is all-in' % (player, fmt(additional))
            else:
                converted = '%s: bets $%s and is all-in' % (player, fmt(total))
                current_facing_bet = total
                last_aggressive = 'bet'
            out.append(converted); continue

        raise_m = re.match(r'(\S+): raises \$([\d.]+) to \$([\d.]+)', line)
        if raise_m:
            player   = raise_m.group(1)
            raise_to = float(raise_m.group(3))
            if pending_call and pending_call[0] == player:
                pending_call = None
            else:
                flush_pending()
            player_invested[player] = raise_to
            current_facing_bet = raise_to
            last_aggressive = 'raise'
            out.append(line); continue

        calls_m = re.match(r'(\S+): calls \$([\d.]+)', line)
        if calls_m:
            flush_pending()
            player, amount = calls_m.group(1), float(calls_m.group(2))
            player_invested[player] = round(player_invested.get(player, 0.0) + amount, 2)
            pending_call = (player, line); continue

        bets_m = re.match(r'(\S+): bets \$([\d.]+)', line)
        if bets_m:
            flush_pending()
            player, amount = bets_m.group(1), float(bets_m.group(2))
            player_invested[player] = float(amount)
            current_facing_bet = float(amount)
            last_aggressive = 'bet'
            out.append(line); continue

        pot_m = re.match(r'Total pot \$([\d.]+) \| Rake \$([\d.]+)', line)
        if pot_m:
            flush_pending()
            adjusted = round(float(pot_m.group(1)) - splash_amount, 2)
            out.append('Total pot $%s | Rake $%s' % (fmt(adjusted), pot_m.group(2)))
            continue

        flush_pending()
        out.append(line)

    flush_pending()
    return '\n'.join(out)


def merge_collected(hand_text):
    lines = hand_text.split('\n')
    collected = {}
    order = []
    for l in lines:
        m = re.match(r'(\S+) collected \$([\d.]+) from pot', l)
        if m:
            p, amt = m.group(1), float(m.group(2))
            if p not in collected:
                collected[p] = 0.0
                order.append(p)
            collected[p] = round(collected[p] + amt, 2)

    if all(hand_text.count(f'{p} collected') == 1 for p in collected):
        return hand_text

    seen = set()
    new_lines = []
    for l in lines:
        m = re.match(r'(\S+) collected \$([\d.]+) from pot', l)
        if m:
            p = m.group(1)
            if p not in seen:
                new_lines.append(f'{p} collected ${fmt(collected[p])} from pot')
                seen.add(p)
        else:
            for p, total in collected.items():
                l = re.sub(
                    r'(Seat \d+: ' + re.escape(p) + r' showed.*?and won \()\$([\d.]+)(\))',
                    lambda mm, t=total: mm.group(1) + f'${fmt(t)}' + mm.group(3),
                    l
                )
            new_lines.append(l)

    return '\n'.join(new_lines)


def convert_file(input_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    raw_blocks = re.split(r'\n{2,}', content.strip())
    converted = []
    hand_buffer = []

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        if re.match(r'Hand #\d+:', block.split('\n')[0]):
            if hand_buffer:
                result = convert_hand('\n'.join(hand_buffer))
                if result:
                    converted.append(merge_collected(result))
                hand_buffer = []
        hand_buffer.append(block)

    if hand_buffer:
        result = convert_hand('\n'.join(hand_buffer))
        if result:
            converted.append(merge_collected(result))

    hands_in  = len(re.findall(r'^Hand #', content, re.M))
    hands_out = len(converted)
    return '\n\n\n'.join(converted) + '\n\n\n', hands_in, hands_out


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 coinpoker_to_pt4.py <coinpoker_export.txt>")
        sys.exit(1)
    input_path = sys.argv[1]
    output_path = str(Path(input_path).stem) + '_PT4.txt'
    print(f"Converting: {input_path}")
    result, hands_in, hands_out = convert_file(input_path)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(result)
    print(f"Hands in source : {hands_in}")
    print(f"Hands converted : {hands_out}")
    print(f"Output file     : {output_path}")
