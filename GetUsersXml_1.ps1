# Функция для определения кодировки файла по сигнатуре BOM или по умолчанию считает windows-1251 (ANSI)
function Get-FileEncoding {
  param([string]$Path)
  $fs = [System.IO.File]::Open($Path, 'Open', 'Read')
  $bytes = New-Object byte[] 4
  $fs.Read($bytes, 0, 4) | Out-Null
  $fs.Close()
  switch -regex ($bytes -join ',') {
    '^239,187,191' { return "utf-8" }
    '^255,254,0,0' { return "utf-32" }
    '^255,254' { return "utf-16" }
    '^254,255' { return "big-endian-unicode" }
    default { return "windows-1251" }
  }
}

# Запрос пользователю
$domainAnswer = Read-Host 'Требуется добавлять пользователей из домена? (Y/N)'
$domainAnswer = $domainAnswer.ToLower()

if ($domainAnswer -eq 'y' -or $domainAnswer -eq 'н') {
  $adGuid = (Get-ADDomain).ObjectGUID.Guid
}
else {
  $adGuid = Read-Host "Введите GUID домена (adGuid)"
}

foreach ($csv in (Get-ChildItem -Path $PWD -Filter '*.csv')) {
  $encoding = Get-FileEncoding $csv.FullName

  $reader = New-Object System.IO.StreamReader($csv.FullName, [System.Text.Encoding]::GetEncoding($encoding))
  $firstLine = $reader.ReadLine()
  $reader.Close()

  if ($firstLine -match ";") { $delimiter = ";" }
  elseif ($firstLine -match ",") { $delimiter = "," }
  else { $delimiter = ";" }

  $bytes = [System.IO.File]::ReadAllBytes($csv.FullName)
  $text = [System.Text.Encoding]::GetEncoding($encoding).GetString($bytes)
  $csvData = $text | ConvertFrom-Csv -Delimiter $delimiter

  $sysConfigXml = @"
<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://monitel.com/2014/schema-sysconfig#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<md:FullModel rdf:about="#_sysconfig">
  <md:Model.created>$(Get-Date -Format s)Z</md:Model.created>
  <md:Model.version>2020-07-09(11.6.2.35)</md:Model.version>
  <me:Model.name xmlns:me="http://monitel.com/2014/schema-cim16#">SysConfig</me:Model.name>
</md:FullModel>
"@

  $energyXml = @"
<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://iec.ch/TC57/2014/CIM-schema-cim16#" xmlns:cim17="http://iec.ch/TC57/2014/CIM-schema-cim17#" xmlns:me="http://monitel.com/2014/schema-cim16#" xmlns:rh="http://rushydro.ru/2015/schema-cim16#" xmlns:so="http://so-ups.ru/2015/schema-cim16#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<md:FullModel rdf:about="#_energy">
  <md:Model.created>$(Get-Date -Format s)Z</md:Model.created>
  <md:Model.version>ver:11.6.2.193;opt:Aggr,AMI,...</md:Model.version>
  <me:Model.name>CIM16</me:Model.name>
</md:FullModel>
"@

  $updatedRows = @()
  foreach ($line in $csvData) {
    $name = $line.name
    $login = $line.login
    $email = $line.email       # Новый столбец email!
    $mobilePhone = $line.mobilePhone # Новый столбец mobilePhone!
    $person_guid = $line.person_guid
    if ([string]::IsNullOrWhiteSpace($person_guid)) {
      $person_guid = [guid]::NewGuid().ToString()
    }
    $parent_sysconfig = $line.parent_sysconfig
    $parent_energy = $line.parent_energy

    $fio = $name -split ' '
    $fio_last = if ($fio.Length -ge 1) { $fio[0] } else { "" }
    $fio_first = if ($fio.Length -ge 2) { $fio[1] } else { "" }
    $fio_middle = if ($fio.Length -ge 3) { $fio[2] } else { "" }

    $sysConfigXml += @"
<cim:User rdf:about="#_$person_guid">
  <cim:Principal.isEnabled>true</cim:Principal.isEnabled>
  <cim:Principal.Domain rdf:resource="#_$adGuid" />
  <cim:User.login>$login</cim:User.login>
  <cim:IdentifiedObject.name>$name</cim:IdentifiedObject.name>
  <cim:IdentifiedObject.ParentObject rdf:resource="#_$parent_sysconfig" />
</cim:User>
"@

    # ==== Формируем блоки с email и телефоном ====
    $emailBlock = ""
    if ($email) {
      $emailBlock = @"
<cim:Person.electronicAddress>
  <cim:ElectronicAddress>
    <cim:ElectronicAddress.email1>$email</cim:ElectronicAddress.email1>
  </cim:ElectronicAddress>
</cim:Person.electronicAddress>
"@
    }
    $phoneBlock = ""
    if ($mobilePhone) {
      $phoneBlock = @"
<cim:Person.mobilePhone>
  <cim:TelephoneNumber>
    <cim:TelephoneNumber.localNumber>$mobilePhone</cim:TelephoneNumber.localNumber>
  </cim:TelephoneNumber>
</cim:Person.mobilePhone>
"@
    }

    # ==== Вставляем в energyXml все нужные данные пользователей ====
    $energyXml += @"
<cim:Person rdf:about="#_$person_guid">
  <cim:IdentifiedObject.name>$name</cim:IdentifiedObject.name>
  <me:IdentifiedObject.ParentObject rdf:resource="#_$parent_energy" />
  $emailBlock
  <cim:Person.firstName>$fio_first</cim:Person.firstName>
  <cim:Person.lastName>$fio_last</cim:Person.lastName>
  <cim:Person.mName>$fio_middle</cim:Person.mName>
  $phoneBlock
</cim:Person>
"@

    $updatedRow = [PSCustomObject]@{
      name             = $name
      login            = $login
      email            = $email
      mobilePhone      = $mobilePhone
      person_guid      = $person_guid
      parent_energy    = $parent_energy
      parent_sysconfig = $parent_sysconfig
    }
    $updatedRows += $updatedRow
  }

  $sysConfigXml += @"
</rdf:RDF>
"@
  $energyXml += @"
</rdf:RDF>
"@

  [System.IO.File]::WriteAllText([IO.Path]::ChangeExtension($csv.FullName, 'sysconfig.xml'), $sysConfigXml, [System.Text.Encoding]::UTF8)
  [System.IO.File]::WriteAllText([IO.Path]::ChangeExtension($csv.FullName, 'energy.xml'), $energyXml, [System.Text.Encoding]::UTF8)

  $exportEncoding = $encoding
  if ($exportEncoding -eq "utf-8") { $exportEncoding = "UTF8" }
  if ($exportEncoding -eq "utf-16") { $exportEncoding = "Unicode" }
  if ($exportEncoding -eq "utf-32") { $exportEncoding = "UTF32" }
  if ($exportEncoding -eq "big-endian-unicode") { $exportEncoding = "BigEndianUnicode" }
  if ($exportEncoding -eq "windows-1251") { $exportEncoding = "Default" }

  $updatedRows | Export-Csv -Path $csv.FullName -Delimiter $delimiter -Encoding $exportEncoding -NoTypeInformation
}

Write-Host "Обработка завершена. Все person_guid записаны в исходные CSV!"
