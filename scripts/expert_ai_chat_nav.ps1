param(
    [Parameter(Mandatory = $true)][long]$WindowHandle,
    [ValidateSet('inspect', 'open', 'send-handoff')][string]$Action = 'inspect',
    [string]$OldConversationUrl = '',
    [string]$ExpectedNewChatUrl = '',
    [string]$HandoffId = ''
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ForegroundCheck {
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
}
'@
$root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$WindowHandle)
if (-not $root) { throw 'Browser window unavailable' }

function All-OfType([System.Windows.Automation.ControlType]$type) {
    $condition = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty, $type)
    return $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
}
function Read-Address {
    $edits = All-OfType ([System.Windows.Automation.ControlType]::Edit)
    foreach ($edit in $edits) {
        if ($edit.Current.Name -notin @('Address and search bar', 'Barra de endereço e pesquisa')) {
            continue
        }
        $pattern = $null
        if ($edit.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
            $address = [string]$pattern.Current.Value
            if ($address -match '^(?:www\.)?chatgpt\.com(?:/|$)') { $address = 'https://' + $address }
            if ($address -match '^https://(?:www\.)?chatgpt\.com(?:/|$)') {
                return ([uri]$address).GetLeftPart([System.UriPartial]::Path).TrimEnd('/')
            }
        }
    }
    return ''
}
$address = Read-Address
if (-not $address -or $address -notmatch '^https://(?:www\.)?chatgpt\.com(?:/|$)') {
    throw 'A valid chatgpt.com address is required'
}
$buttons = All-OfType ([System.Windows.Automation.ControlType]::Button)
$composer = @()
foreach ($edit in (All-OfType ([System.Windows.Automation.ControlType]::Edit))) {
    if (($edit.Current.Name -in @('Pergunte ao ChatGPT','Ask ChatGPT','Ask anything','Message ChatGPT')) -and (-not $edit.Current.IsOffscreen)) { $composer += $edit }
}
$notice = @()
$handoffMarkerPresent = $false
foreach ($control in (All-OfType ([System.Windows.Automation.ControlType]::Text))) {
    if ($control.Current.IsOffscreen) { continue }
    $name = [string]$control.Current.Name
    if ($HandoffId -and $name.Contains("[migration_id: $HandoffId]")) {
        $handoffMarkerPresent = $true
    }
    if ($name.Length -gt 0 -and $name.Length -lt 225 -and
        $name -notmatch '(?i)(request_id|migration_id|CONTINUAR OLIVERS)' -and
        $name -match '(?i)(limit|limite|length|longo|longa|maximum|reached|atingiu|too many|delivery timed out)') {
        $notice += $name.Substring(0, [Math]::Min(360, $name.Length))
        if ($notice.Count -ge 20) { break }
    }
}
$newButtons = @()
$sendButtons = @()
foreach ($button in $buttons) {
    $c = $button.Current
    if ($c.IsOffscreen -or -not $c.IsEnabled) { continue }
    $rect = $c.BoundingRectangle
    if (($c.Name -in @('New chat','Nova conversa','Novo chat')) -and (-not $rect.IsEmpty) -and $rect.Width -ge 70 -and $rect.Height -ge 20) {
        $newButtons += $button
    }
    if ($c.Name -in @('Send','Send message','Enviar','Enviar mensagem') -and $composer.Count -eq 1) {
        $b = $composer[0].Current.BoundingRectangle
        if (-not $rect.IsEmpty -and $rect.Y -ge ($b.Y - 35) -and $rect.Y -le ($b.Y + $b.Height + 35) -and $rect.X -ge ($b.X + $b.Width - 10) -and $rect.X -le ($b.X + $b.Width + 150)) {
            $sendButtons += $button
        }
    }
}
$invoked = $false
if ($Action -ne 'inspect') {
    if ([ForegroundCheck]::GetForegroundWindow() -ne [IntPtr]$WindowHandle) {
        throw 'Browser lost foreground focus'
    }
    if ($OldConversationUrl -and $Action -eq 'open' -and $address -ne $OldConversationUrl) {
        throw 'Calibrated old conversation URL changed'
    }
    if ($Action -eq 'send-handoff' -and $ExpectedNewChatUrl -and $address -ne $ExpectedNewChatUrl) {
        throw 'New chat URL changed before handoff Send'
    }
    if ($OldConversationUrl -and $Action -eq 'send-handoff' -and $address -eq $OldConversationUrl) {
        throw 'Still in previous conversation; refusing handoff'
    }
    if ($Action -eq 'open') {
        if ($newButtons.Count -ne 1) { throw "Expected one visible New chat button; found $($newButtons.Count)" }
        $pattern = $newButtons[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
        $pattern.Invoke()
        $invoked = $true
    }
    if ($Action -eq 'send-handoff') {
        if (-not $HandoffId) { throw 'Missing handoff identifier' }
        if ($composer.Count -ne 1) { throw 'Expected one composer in new conversation' }
        $value = $null
        if (-not $composer[0].TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$value)) {
            throw 'Cannot verify the new chat draft'
        }
        $draft = [string]$value.Current.Value
        if (-not $draft.Contains("[migration_id: $HandoffId]")) {
            throw 'Handoff identifier not present in draft'
        }
        if ($sendButtons.Count -ne 1) {
            throw "Expected exactly one enabled Send button; found $($sendButtons.Count)"
        }
        $pattern = $sendButtons[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
        $pattern.Invoke()
        $invoked = $true
    }
}
[pscustomobject]@{
    url = $address
    composer_count = $composer.Count
    new_chat_count = $newButtons.Count
    send_count = $sendButtons.Count
    visible_notices = @($notice)
    handoff_marker_present = [bool]$handoffMarkerPresent
    invoked = $invoked
} | ConvertTo-Json -Compress -Depth 4
