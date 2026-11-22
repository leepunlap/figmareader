#!/usr/bin/env swift
// axfind — locate accessibility elements by title/description substring and
// optionally press or click them.
//
//   axfind "Lion"                  # list matches with position/size
//   axfind "Lion" press            # AXPress the best match
//   axfind "Lion" click            # real CGEvent click at the element centre
//
// Figma renders its UI inside a Chromium view, so the page list, layer names
// and buttons are all AX-exposed with real on-screen geometry.

import Foundation
import AppKit
import ApplicationServices
import CoreGraphics

// MARK: - AX helpers

func copyAttr(_ el: AXUIElement, _ attr: String) -> CFTypeRef? {
    var value: CFTypeRef?
    let err = AXUIElementCopyAttributeValue(el, attr as CFString, &value)
    return err == .success ? value : nil
}

func attrString(_ el: AXUIElement, _ attr: String) -> String? {
    guard let v = copyAttr(el, attr) else { return nil }
    return (v as? String) ?? ((v as? NSString) as String?)
}

func attrPoint(_ el: AXUIElement, _ attr: String) -> CGPoint? {
    guard let v = copyAttr(el, attr) else { return nil }
    guard CFGetTypeID(v) == AXValueGetTypeID() else { return nil }
    var p = CGPoint.zero
    guard AXValueGetValue(v as! AXValue, .cgPoint, &p) else { return nil }
    return p
}

func attrSize(_ el: AXUIElement, _ attr: String) -> CGSize? {
    guard let v = copyAttr(el, attr) else { return nil }
    guard CFGetTypeID(v) == AXValueGetTypeID() else { return nil }
    var s = CGSize.zero
    guard AXValueGetValue(v as! AXValue, .cgSize, &s) else { return nil }
    return s
}

func textOf(_ el: AXUIElement) -> String {
    var out: [String] = []
    for attr in [kAXTitleAttribute as String,
                 kAXDescriptionAttribute as String,
                 kAXValueAttribute as String,
                 kAXHelpAttribute as String] {
        if let s = attrString(el, attr), !s.isEmpty { out.append(s) }
    }
    return out.joined(separator: " | ")
}

func roleOf(_ el: AXUIElement) -> String {
    attrString(el, kAXRoleAttribute as String) ?? "?"
}

func pidFor(_ name: String) -> pid_t? {
    if let ws = NSWorkspace.shared.runningApplications.first(where: {
        ($0.localizedName ?? "").localizedCaseInsensitiveContains(name)
    }) { return ws.processIdentifier }
    return nil
}

// MARK: - walk

struct Hit {
    let el: AXUIElement
    let text: String
    let pos: CGPoint
    let size: CGSize
    let role: String
}

var hits: [Hit] = []

func walk(_ el: AXUIElement, needle: String, depth: Int) {
    guard depth < 16 else { return }
    let t = textOf(el)
    if !t.isEmpty, t.lowercased().contains(needle.lowercased()),
       let p = attrPoint(el, kAXPositionAttribute as String),
       let s = attrSize(el, kAXSizeAttribute as String) {
        hits.append(Hit(el: el, text: t, pos: p, size: s, role: roleOf(el)))
    }
    guard let v = copyAttr(el, kAXChildrenAttribute as String),
          let kids = v as? [AXUIElement] else { return }
    for k in kids { walk(k, needle: needle, depth: depth + 1) }
}

// MARK: - main

var args = Array(CommandLine.arguments.dropFirst())
var appName = "Figma"
if args.first == "--app" { args.removeFirst(); appName = args.removeFirst() }
var action = "list"
if args.first == "press" || args.first == "click" { action = args.removeFirst() }
let needle = args.first ?? ""

guard let pid = pidFor(appName) else {
    FileHandle.standardError.write("no process \(appName)\n".data(using: .utf8)!)
    exit(2)
}

let app = AXUIElementCreateApplication(pid)
walk(app, needle: needle, depth: 0)

if hits.isEmpty {
    print("no match for '\(needle)'")
    exit(1)
}

if action == "list" {
    for h in hits.prefix(30) {
        print("\(h.role) '\(h.text)' @(\(Int(h.pos.x)),\(Int(h.pos.y))) \(Int(h.size.width))x\(Int(h.size.height))")
    }
    exit(0)
}

// prefer the tightest element that actually contains the needle text
let best = hits.min { a, b in
    let aa = a.size.width * a.size.height
    let bb = b.size.width * b.size.height
    if abs(aa - bb) < 1 { return a.text.count < b.text.count }
    return aa < bb
}!

if action == "press" {
    if AXUIElementPerformAction(best.el, kAXPressAction as CFString) == .success {
        print("pressed '\(best.text)' @(\(Int(best.pos.x)),\(Int(best.pos.y)))")
        exit(0)
    }
    print("AXPress failed for '\(best.text)'")
    exit(3)
}

let cx = best.pos.x + best.size.width / 2
let cy = best.pos.y + best.size.height / 2

func post(_ type: CGEventType, _ x: Double, _ y: Double) {
    guard let ev = CGEvent(mouseEventSource: nil, mouseType: type,
                           mouseCursorPosition: CGPoint(x: x, y: y),
                           mouseButton: .left) else { return }
    ev.post(tap: .cghidEventTap)
}
post(.mouseMoved, cx, cy)
usleep(150_000)
post(.leftMouseDown, cx, cy)
usleep(70_000)
post(.leftMouseUp, cx, cy)
print("clicked '\(best.text)' @(\(Int(cx)),\(Int(cy)))")
