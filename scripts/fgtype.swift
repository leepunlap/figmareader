#!/usr/bin/env swift
// fgtype — type a literal string into the frontmost app (CoreGraphics key events).
//
// The Figma save panel and macOS dialogs need real keystrokes: AX keystrokes
// do not reach them, and AppleScript "keystroke" is unreliable for paths.
//
//   fgtype "/Users/blee/src/figma/source/v1raw"
//   fgtype --key return
//   fgtype --key tab
//
// Non-ASCII is typed through the Unicode keyboard path (cmd+shift+u is not
// available here), so this is ASCII-only by design.

import Foundation
import CoreGraphics

func keyDown(_ code: UInt16) {
    CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: true)?.post(tap: .cghidEventTap)
}
func keyUp(_ code: UInt16) {
    CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: false)?.post(tap: .cghidEventTap)
}

let SPECIAL: [String: UInt16] = [
    "return": 0x24, "enter": 0x24, "tab": 0x30, "escape": 0x35, "esc": 0x35,
    "space": 0x31, "delete": 0x33, "backspace": 0x33, "left": 0x7B, "right": 0x7C,
    "down": 0x7D, "up": 0x7E, "home": 0x73, "end": 0x77, "pageup": 0x74,
    "pagedown": 0x79,
]

// US ANSI layout: character -> virtual key code
let KEYCODE: [Character: UInt16] = {
    var m: [Character: UInt16] = [:]
    let letters = Array("abcdefghijklmnopqrstuvwxyz")
    for (i, c) in letters.enumerated() { m[c] = UInt16(0x00 + i) }
    let upper = Array("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    for (i, c) in upper.enumerated() { m[c] = UInt16(0x00 + i) }
    let digits = Array("0123456789")
    for (i, c) in digits.enumerated() { m[c] = UInt16(0x1D + i) }
    let punct: [Character: UInt16] = [
        "-": 0x1E, "=": 0x1F, "[": 0x21, "]": 0x22, "\\": 0x2A, ";": 0x2B,
        "'": 0x27, ",": 0x2C, ".": 0x2E, "/": 0x2F, "`": 0x32,
    ]
    for (k, v) in punct { m[k] = v }
    return m
}()

let SHIFTED: Set<Character> = [
    "A","B","C","D","E","F","G","H","I","J","K","L","M","N","O","P","Q","R","S",
    "T","U","V","W","X","Y","Z","!","@","#","$","%","^","&","*","(",")","_","+",
    "{","|","}",":","\"","<",">","?","~",
]

let SHIFT_CODE: UInt16 = 0x38

var args = Array(CommandLine.arguments.dropFirst())
if args.isEmpty {
    print("usage: fgtype <text> | fgtype --key <name>")
    exit(1)
}

if args[0] == "--key" {
    guard args.count >= 2, let code = SPECIAL[args[1].lowercased()] else {
        print("unknown key: \(args.count > 1 ? args[1] : "")")
        exit(1)
    }
    keyDown(code); usleep(30_000); keyUp(code)
    usleep(60_000)
    exit(0)
}

let text = args.joined(separator: " ")
for ch in text {
    if ch == "~" {
        keyDown(SHIFT_CODE); keyDown(0x32); usleep(20_000); keyUp(0x32); keyUp(SHIFT_CODE)
        usleep(20_000)
        continue
    }
    guard let code = KEYCODE[ch] else { continue }
    if SHIFTED.contains(ch) {
        keyDown(SHIFT_CODE); usleep(10_000)
        keyDown(code); usleep(20_000); keyUp(code)
        usleep(10_000); keyUp(SHIFT_CODE)
    } else {
        keyDown(code); usleep(20_000); keyUp(code)
    }
    usleep(25_000)
}
usleep(80_000)
