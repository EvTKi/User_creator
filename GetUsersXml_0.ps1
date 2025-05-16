$adGuid = (Get-ADDomain).ObjectGUID.Guid

foreach ( $csv in (Get-ChildItem -Path $PWD -Filter '*.csv') )
{
    $sysConfigFolderGuid = (New-Guid).Guid
    $energyFolderGuid = (New-Guid).Guid

    $sysConfigXml = @"
<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://monitel.com/2014/schema-sysconfig#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <md:FullModel rdf:about="#_5feb434e-bd7d-441c-b738-23cb609266e2">
    <md:Model.created>2021-02-17T07:13:12.7547787Z</md:Model.created>
    <md:Model.version>2020-07-09(11.6.2.35)</md:Model.version>
    <me:Model.name xmlns:me="http://monitel.com/2014/schema-cim16#">SysConfig</me:Model.name>
  </md:FullModel>
  <cim:Folder rdf:about="#_$( $sysConfigFolderGuid )">
    <cim:IdentifiedObject.name>Новые пользователи ОЖ</cim:IdentifiedObject.name>
    <cim:IdentifiedObject.ParentObject rdf:resource="#_$( $adGuid )" />
    <cim:Folder.CreatingNode rdf:resource="#_0cd54341-67c8-45ea-9961-dc29a9e2c3df" />
  </cim:Folder>

"@

    $energyXml = @"
<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://iec.ch/TC57/2014/CIM-schema-cim16#" xmlns:cim17="http://iec.ch/TC57/2014/CIM-schema-cim17#" xmlns:me="http://monitel.com/2014/schema-cim16#" xmlns:rh="http://rushydro.ru/2015/schema-cim16#" xmlns:so="http://so-ups.ru/2015/schema-cim16#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <md:FullModel rdf:about="#_57e8b753-bcf1-4c2a-8d12-4ff72e5e3870">
    <md:Model.created>2021-02-17T07:31:28.6639253Z</md:Model.created>
    <md:Model.version>ver:11.6.2.193;opt:Aggr,AMI,BaseRep,CI,CIMW,CM,CrM,CrT,dLog,DomainSync,EGTS,eLogClt,eNote,GIS,HIS,IEC104,InfoLift,IntegSWEO,LoadShed,MAGSM,MAGT,MClipper,MM,MNetBC,MNetCW,MNetSC,MoMS,MVCS,NetTracing,OCMon,OLP,ONC,OR,OrdM,OutCall,OutEx,OutReq,PF,PL,RapidBus,Rep,RT_SE,RT_TP,SCADA,SCADA_DN,SCADA_HS,SE_PC,SwM,TNATerm,TNEq,TP,TPL,TTPL,VA,VMon,WebMag;</md:Model.version>
    <me:Model.name>CIM16</me:Model.name>
  </md:FullModel>
  <me:Folder rdf:about="#_$( $energyFolderGuid )">
    <cim:IdentifiedObject.name>Новые пользователи ОЖ</cim:IdentifiedObject.name>
    <me:IdentifiedObject.ParentObject rdf:resource="#_00000001-0000-0000-c000-0000006d746c" />
    <me:Folder.CreatingNode rdf:resource="#_4a5a63e6-7a52-49f9-8a83-8537be45409a" />
  </me:Folder>

"@

    Get-Content $csv.FullName |
        ConvertFrom-Csv |
        ForEach-Object {
            $u = Get-ADUser -Filter "sAMAccountName -eq '$( $PSItem.name )'"
            if ( $null -eq $u )
            {
                Write-Host "User '$( $PSItem.name )' not found" -ForegroundColor Red
                return
            }
            $sysConfigXml += @"
  <cim:User rdf:about="#_$( $u.ObjectGUID )">
    <cim:Principal.isEnabled>true</cim:Principal.isEnabled>
    <cim:Principal.Domain rdf:resource="#_$( $adGuid )" />
    <cim:User.login>$( $u.SamAccountName )</cim:User.login>
    <cim:IdentifiedObject.name>$( $u.Name )</cim:IdentifiedObject.name>
    <cim:IdentifiedObject.ParentObject rdf:resource="#_$( $sysConfigFolderGuid )" />
  </cim:User>
"@
            $energyXml += @"
  <cim:Person rdf:about="#_$( $u.ObjectGUID )">
    <cim:Person.firstName>$( $u.GivenName )</cim:Person.firstName>
    <cim:Person.lastName>$( $u.Surname )</cim:Person.lastName>
    <cim:Person.mName>$( ($u.Name -split ' ')[2] )</cim:Person.mName>
    <cim:IdentifiedObject.name>$( $u.Name )</cim:IdentifiedObject.name>
    <me:IdentifiedObject.ParentObject rdf:resource="#_$( $energyFolderGuid )" />
  </cim:Person>
"@
        }

    $sysConfigXml += @"

</rdf:RDF>
"@

    $sysConfigXml | Out-File ([IO.Path]::ChangeExtension($csv, 'sysconfig.xml')) -Encoding utf8

    $energyXml += @"

</rdf:RDF>
"@

    $energyXml | Out-File ([IO.Path]::ChangeExtension($csv, 'energy.xml')) -Encoding utf8
}