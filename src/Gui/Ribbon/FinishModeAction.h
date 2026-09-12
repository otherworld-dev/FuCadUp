/***************************************************************************
 *   Copyright (c) 2026 FuCad contributors                                 *
 *                                                                         *
 *   This file is part of FreeCAD.                                         *
 *                                                                         *
 *   FreeCAD is free software: you can redistribute it and/or modify it    *
 *   under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1 of the  *
 *   License, or (at your option) any later version.                       *
 *                                                                         *
 *   FreeCAD is distributed in the hope that it will be useful, but        *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
 *   Lesser General Public License for more details.                       *
 *                                                                         *
 *   You should have received a copy of the GNU Lesser General Public      *
 *   License along with FreeCAD. If not, see                               *
 *   <https://www.gnu.org/licenses/>.                                      *
 *                                                                         *
 ***************************************************************************/


#pragma once

#include <QAction>
#include <QPointer>
#include <QString>

#include <FCGlobal.h>

namespace Gui
{
namespace Ribbon
{

/**
 * What an entry of an ordinary ribbon tab shows for its command while a mode
 * that knows how to finish itself is running, such as editing a sketch.
 *
 * The command itself usually stands down for the mode, and has to: it may own a
 * bare letter the mode needs for its own tools. The stand-in carries the
 * command's icon, text and tooltip but no shortcut, and stays clickable for as
 * long as the mode can be finished. A click finishes the mode through its finish
 * command and then runs the command, the way Fusion's SOLID tab works from
 * inside a sketch.
 * @author FuCad contributors
 */
class GuiExport FinishModeAction: public QAction
{
public:
    /**
     * Stands in for \a source while \a finishCommand can end the running mode.
     * With \a keepEdited the command starts with the object the mode was editing
     * selected, which is how Extrude is handed the sketch just finished; without
     * it the command starts with nothing selected.
     */
    FinishModeAction(QAction* source, const QString& finishCommand, bool keepEdited, QObject* parent);
    ~FinishModeAction() override = default;

private:
    /// Copies the state the command framework keeps up to date on the source.
    void followSource();
    void run();

    QPointer<QAction> source;
    QPointer<QAction> finish;
    QString finishCommand;
    bool keepEdited {false};

    Q_DISABLE_COPY(FinishModeAction)
};

}  // namespace Ribbon
}  // namespace Gui
