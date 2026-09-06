/*
FuCadUp Installer Language File
Language: Portuguese
*/

!insertmacro LANGFILE_EXT "Portuguese"

${LangFileString} TEXT_INSTALL_CURRENTUSER "(Instalado para o Utilizador Atual)"

${LangFileString} TEXT_WELCOME "Este assistente de instalação irá guiá-lo através da instalação do FuCadUp.$\r$\n\
				$\r$\n\
				$_CLICK"

#${LangFileString} TEXT_CONFIGURE_PYTHON "Compilando os scripts de Python..."

${LangFileString} TEXT_FINISH_DESKTOP "Criar um atalho no ambiente de trabalho"
${LangFileString} TEXT_FINISH_WEBSITE "Visite github.com/otherworld-dev/FuCadUp para as últimas notícias, suporte e dicas"

#${LangFileString} FileTypeTitle "Documento FuCadUp"

#${LangFileString} SecAllUsersTitle "Instalar para todos os utilizadores?"
${LangFileString} SecFileAssocTitle "Associação dos ficheiros"
${LangFileString} SecDesktopTitle "Icone do ambiente de trabalho"

${LangFileString} SecCoreDescription "Os ficheiros FuCadUp."
#${LangFileString} SecAllUsersDescription "Instalar o FuCadUp para todos os utilizadores ou apenas para o presente utilizador."
${LangFileString} SecFileAssocDescription "Os ficheiros com a extensão .FCStd irão abrir automaticamente no FuCadUp."
${LangFileString} SecDesktopDescription "Um icone do FuCadUp no ambiente de trabalho."
#${LangFileString} SecDictionaries "Dicionários"
#${LangFileString} SecDictionariesDescription "Dicionários do corretor ortográfico que podem ser descarregados e instalados."

#${LangFileString} PathName 'Caminho ao ficheiro $\"xxx.exe$\"'
#${LangFileString} InvalidFolder 'O ficheiro $\"xxx.exe$\" não está no caminho especificado.'

#${LangFileString} DictionariesFailed 'Falha ao descarregar o dicionário para o idioma $\"$R3$\".'

#${LangFileString} ConfigInfo "A configuração seguinte do FuCadUp irá demorar um bocado."

#${LangFileString} RunConfigureFailed "Não foi possível executar o script de configuração"
${LangFileString} InstallRunning "O instalador já está a correr!"
${LangFileString} AlreadyInstalled "O FuCadUp ${APP_SERIES_KEY2} já está instalado!$\r$\n\
				Quer continuar na mesma a instalar o FuCadUp sobre a versão existente?"
${LangFileString} NewerInstalled "Está a tentar instalar uma versão mais antiga do que a que tem instalada.$\r$\n\
				  Se realmente quer fazer isto deve antes desinstalar o FuCadUp $OldVersionNumber."

#${LangFileString} FinishPageMessage "Parabéns! O FuCadUp foi instalado com sucesso.$\r$\n\
#					$\r$\n\
#					(O primeiro início do FuCadUp pode levar alguns segundos.)"
${LangFileString} FinishPageRun "Lançar o FuCadUp"

${LangFileString} UnNotInRegistryLabel "Incapaz de encontrar o FuCadUp no registry.$\r$\n\
					Os atalhos para o ambiente de trabalho no menu Start não serão removidos."
${LangFileString} UnInstallRunning "Deve fechar o FuCadUp em primeiro lugar!"
${LangFileString} UnNotAdminLabel "Precisa de privilégios de administrador para desinstalar o FuCadUp!"
${LangFileString} UnReallyRemoveLabel "Tem a certeza que quer remover completamente o FuCadUp e todas as suas componentes?"
${LangFileString} UnFuCadUpPreferencesTitle 'Preferências de utilizador do FuCadUp'

#${LangFileString} SecUnProgDescription "Desinstala xxx."
${LangFileString} SecUnPreferencesDescription 'Apaga as pastas de configuração do  FuCadUp$\r$\n\
						$\"$AppPre\username\$\r$\n\
						$AppSuff\$\r$\n\
						${APP_DIR_USERDATA}$\")$\r$\n\
						de todos os utilizadores.'
${LangFileString} DialogUnPreferences 'You chose to delete the FuCadUps user configuration.$\r$\n\
						This will also delete all installed FuCadUp addons.$\r$\n\
						Do you agree with this?'
${LangFileString} SecUnProgramFilesDescription "Desinstala FuCadUp e todas as suas componentes."

${LangFileString} DirNotEmptyWarning "The selected folder '$INSTDIR' is not empty.$\r$\n\
                        The installer will remove all its content before installing. Continue?"
${LangFileString} RMInstDirFailed "Failed to remove '$INSTDIR'.$\r$\n\
                        Make sure you have sufficient permissions and that no files are in use."
