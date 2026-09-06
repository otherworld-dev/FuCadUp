/*
FuCadUp Installer Language File
Language: Spanish
*/

!insertmacro LANGFILE_EXT "Spanish"

${LangFileString} TEXT_INSTALL_CURRENTUSER "(Instalado para el actual usuario)"

${LangFileString} TEXT_WELCOME "Este programa instalará FuCadUp en su ordenador.$\r$\n\
				$\r$\n\
				$_CLICK"

#${LangFileString} TEXT_CONFIGURE_PYTHON "Compilando guiones Python..."

${LangFileString} TEXT_FINISH_DESKTOP "Crear acceso directo en el escritorio"
${LangFileString} TEXT_FINISH_WEBSITE "Visite github.com/otherworld-dev/FuCadUp para últimas noticias, ayuda y consejos"

#${LangFileString} FileTypeTitle "Documento FuCadUp"

#${LangFileString} SecAllUsersTitle "Instalar para todos los usuarios"
${LangFileString} SecFileAssocTitle "Asociar ficheros"
${LangFileString} SecDesktopTitle "Icono de escritorio"

${LangFileString} SecCoreDescription "Los ficheros de FuCadUp."
#${LangFileString} SecAllUsersDescription "Instalar FuCadUp para todos los usuarios o sólo para el usuario actual."
${LangFileString} SecFileAssocDescription "Asociar la extensión .FCStd con FuCadUp."
${LangFileString} SecDesktopDescription "Crear un icono de FuCadUp en el escritorio."
#${LangFileString} SecDictionaries "Diccionarios"
#${LangFileString} SecDictionariesDescription "Diccionarios de revisión ortográfica que se pueden descargar e instalar."

#${LangFileString} PathName 'Ruta al fichero $\"xxx.exe$\"'
#${LangFileString} InvalidFolder 'Imposible encontrar $\"xxx.exe$\".'

#${LangFileString} DictionariesFailed 'La descarga del diccionario para el idioma $\"$R3$\" ha fallado.'

#${LangFileString} ConfigInfo "La siguiente configuración de FuCadUp va a tardar un poco."

#${LangFileString} RunConfigureFailed "Error al intentar ejecutar el programa de configuración"
${LangFileString} InstallRunning "El instalador ya está siendo ejecutado!"
${LangFileString} AlreadyInstalled "¡FuCadUp ${APP_SERIES_KEY2} ya está instalado!$\r$\n\
				Aún así, ¿quiere instalar FuCadUp sobre la versión existente?"
${LangFileString} NewerInstalled "Está tratando de instalar una versión de FuCadUp más antigua que la que tiene instalada.$\r$\n\
				  Si realmente lo desea, debe desinstalar antes la versión de FuCadUp instalada $OldVersionNumber."

#${LangFileString} FinishPageMessage "¡Enhorabuena! FuCadUp ha sido instalado con éxito.$\r$\n\
#					$\r$\n\
#					(El primer arranque de FuCadUp puede tardar algunos segundos.)"
${LangFileString} FinishPageRun "Ejecutar FuCadUp"

${LangFileString} UnNotInRegistryLabel "Imposible encontrar FuCadUp en el registro.$\r$\n\
					Los accesos rápidos del escritorio y del Menú de Inicio no serán eliminados."
${LangFileString} UnInstallRunning "Antes cierre FuCadUp!"
${LangFileString} UnNotAdminLabel "Necesita privilegios de administrador para desinstalar FuCadUp!"
${LangFileString} UnReallyRemoveLabel "¿Está seguro de que desea eliminar completamente FuCadUp y todos sus componentes?"
${LangFileString} UnFuCadUpPreferencesTitle 'Preferencias de usuario de FuCadUp'

#${LangFileString} SecUnProgDescription "Desinstala xxx."
${LangFileString} SecUnPreferencesDescription 'Elimina las carpetas de configuración de FuCadUp$\r$\n\
						$\"$AppPre\username\$\r$\n\
						$AppSuff\$\r$\n\
						${APP_DIR_USERDATA}$\")$\r$\n\
						de todos los usuarios.'
${LangFileString} DialogUnPreferences 'Eligió eliminar la configuración de usuario de FuCadUp.$\r$\n\
						Esto también eliminará todos los addons de FuCadUp instalados.$\r$\n\
						¿Está de acuerdo con esto?'
${LangFileString} SecUnProgramFilesDescription "Desinstala FuCadUp y todos sus componentes."

${LangFileString} DirNotEmptyWarning "La carpeta seleccionada '$INSTDIR' no está vacia.$\r$\n\
                        El instalador eliminará todo su contenido antes de instalar. ¿Continuar?"
${LangFileString} RMInstDirFailed "No se ha podido eliminar '$INSTDIR'.$\r$\n\
                        Asegúrese de tener suficientes permisos y que ningún archivo esté en use."
