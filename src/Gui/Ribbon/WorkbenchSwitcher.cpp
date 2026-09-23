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


#include <algorithm>

#include <QCursor>
#include <QFont>
#include <QKeyEvent>
#include <QLineEdit>
#include <QListWidget>
#include <QListWidgetItem>
#include <QScreen>
#include <QVBoxLayout>

#include <App/Application.h>
#include <Base/Parameter.h>
#include <Gui/Application.h>
#include <Gui/MainWindow.h>
#include <Gui/PreferencePages/DlgSettingsWorkbenchesImp.h>
#include <Gui/WorkbenchManager.h>

#include "WorkbenchSwitcher.h"


using namespace Gui;
using namespace Gui::Ribbon;

namespace
{
constexpr int switcherWidth = 280;
constexpr int iconExtent = 20;
constexpr int shownRecent = 3;
constexpr int keptRecent = 8;
constexpr int cursorGap = 12;

const char* const ribbonParameters = "User parameter:BaseApp/Preferences/Ribbon";
const char* const recentKey = "RecentWorkbenches";

// The workbench an item switches to. Captions carry none.
constexpr int workbenchRole = Qt::UserRole;

ParameterGrp::handle parameters()
{
    return App::GetApplication().GetParameterGroupByPath(ribbonParameters);
}

QStringList& recentList()
{
    static QStringList recent = []() {
        const std::string stored = parameters()->GetASCII(recentKey, "");
        return QString::fromLatin1(stored.c_str()).split(QLatin1Char(','), Qt::SkipEmptyParts);
    }();
    return recent;
}

/// "SHEET METAL" as "Sheet Metal": a tab title reads as a list entry.
QString asListEntry(const QString& title)
{
    QStringList words = title.toLower().split(QLatin1Char(' '), Qt::SkipEmptyParts);
    for (QString& word : words) {
        word[0] = word[0].toUpper();
    }
    return words.join(QLatin1Char(' '));
}
}  // namespace


WorkbenchSwitcher* WorkbenchSwitcher::_instance = nullptr;

WorkbenchSwitcher::WorkbenchSwitcher()
    : QWidget(getMainWindow(), Qt::Popup)
{
    setObjectName(QStringLiteral("WorkbenchSwitcher"));
    setAttribute(Qt::WA_StyledBackground, true);
    setFixedWidth(switcherWidth);

    auto* layout = new QVBoxLayout(this);
    layout->setContentsMargins(8, 8, 8, 8);
    layout->setSpacing(6);

    filter = new QLineEdit(this);
    filter->setObjectName(QStringLiteral("WorkbenchSwitcherFilter"));
    filter->setPlaceholderText(tr("Find a workbench"));
    filter->setClearButtonEnabled(true);
    // The field keeps the caret, so the keys that walk the list are taken from
    // it before it spends them on the caret.
    filter->installEventFilter(this);
    layout->addWidget(filter);

    list = new QListWidget(this);
    list->setObjectName(QStringLiteral("WorkbenchSwitcherList"));
    list->setIconSize(QSize(iconExtent, iconExtent));
    list->setFrameShape(QFrame::NoFrame);
    list->setFocusPolicy(Qt::NoFocus);
    list->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    layout->addWidget(list);

    connect(filter, &QLineEdit::textChanged, this, [this]() {
        rebuild();
        if (isVisible()) {
            fitToList(QWidget::screen());
        }
    });
    connect(list, &QListWidget::itemClicked, this, [this](QListWidgetItem* item) {
        activate(item);
    });
}

WorkbenchSwitcher* WorkbenchSwitcher::instance()
{
    if (!_instance) {
        _instance = new WorkbenchSwitcher();
    }

    return _instance;
}

void WorkbenchSwitcher::destruct()
{
    delete _instance;
    _instance = nullptr;
}

void WorkbenchSwitcher::noteWorkbenchUsed(const QString& workbench)
{
    if (workbench.isEmpty()) {
        return;
    }

    QStringList& recent = recentList();
    if (!recent.isEmpty() && recent.front() == workbench) {
        return;
    }

    recent.removeAll(workbench);
    recent.prepend(workbench);
    while (recent.size() > keptRecent) {
        recent.removeLast();
    }

    parameters()->SetASCII(recentKey, recent.join(QLatin1Char(',')).toLatin1().constData());
}

QStringList WorkbenchSwitcher::recentWorkbenches()
{
    return recentList();
}

void WorkbenchSwitcher::setAreas(const std::vector<Area>& value)
{
    areas = value;
}

QString WorkbenchSwitcher::titleFor(const QString& workbench) const
{
    for (const Area& area : areas) {
        if (area.workbench == workbench) {
            return area.title;
        }
    }

    const QString own = Application::Instance->workbenchMenuText(workbench);
    return own.isEmpty() ? workbench : own;
}

void WorkbenchSwitcher::popUp(QWidget* anchor)
{
    filter->clear();
    rebuild();
    fitToList(anchor ? anchor->screen() : QWidget::screen());

    QPoint origin;
    if (anchor) {
        origin = anchor->mapToGlobal(QPoint(0, anchor->height()));
    }
    else {
        const QPoint cursor = QCursor::pos();
        origin = QPoint(cursor.x() - width() / 2, cursor.y() + cursorGap);
    }

    if (const QScreen* screen = anchor ? anchor->screen() : QWidget::screen()) {
        const QRect available = screen->availableGeometry();
        origin.setX(std::clamp(origin.x(), available.left(), available.right() - width()));
        origin.setY(std::clamp(origin.y(), available.top(), available.bottom() - height()));
    }

    move(origin);
    show();
    filter->setFocus(Qt::PopupFocusReason);
}

void WorkbenchSwitcher::fitToList(const QScreen* screen)
{
    // As tall as the rows need, so a narrowed list does not leave an empty
    // panel under it, and no taller than the screen.
    int rows = 0;
    for (int i = 0; i < list->count(); ++i) {
        rows += list->sizeHintForRow(i);
    }
    int wanted = rows + 2 * list->frameWidth() + 4;
    if (screen) {
        const int chrome = height() - list->height();
        wanted = std::min(wanted, screen->availableGeometry().height() - std::max(chrome, 0));
    }
    list->setFixedHeight(std::max(wanted, 0));
    adjustSize();
}

void WorkbenchSwitcher::rebuild()
{
    list->clear();

    const QStringList enabled = Dialog::DlgSettingsWorkbenchesImp::getEnabledWorkbenches();
    const QString active = QString::fromStdString(WorkbenchManager::instance()->activeName());
    const QString query = filter->text().trimmed();

    if (!query.isEmpty()) {
        // One flat list of matches, those that start with the query first, so
        // Enter takes the workbench most likely meant.
        QStringList candidates;
        for (const Area& area : areas) {
            if (enabled.contains(area.workbench)) {
                candidates.append(area.workbench);
            }
        }
        QStringList others = enabled;
        std::sort(others.begin(), others.end(), [this](const QString& a, const QString& b) {
            return titleFor(a).compare(titleFor(b), Qt::CaseInsensitive) < 0;
        });
        for (const QString& workbench : others) {
            if (!candidates.contains(workbench)) {
                candidates.append(workbench);
            }
        }

        QStringList starting;
        QStringList containing;
        for (const QString& workbench : candidates) {
            // An area is found by its own name too, so "part" still finds SOLID.
            const QString title = titleFor(workbench);
            const QString own = Application::Instance->workbenchMenuText(workbench);
            if (title.startsWith(query, Qt::CaseInsensitive)
                || own.startsWith(query, Qt::CaseInsensitive)) {
                starting.append(workbench);
            }
            else if (title.contains(query, Qt::CaseInsensitive)
                     || own.contains(query, Qt::CaseInsensitive)) {
                containing.append(workbench);
            }
        }

        for (const QString& workbench : starting + containing) {
            addWorkbench(workbench, active);
        }
        moveCurrent(1);
        return;
    }

    QStringList listed;

    bool captioned = false;
    for (const Area& area : areas) {
        if (!enabled.contains(area.workbench)) {
            continue;
        }
        if (!captioned) {
            addCaption(tr("Ribbon"));
            captioned = true;
        }
        addWorkbench(area.workbench, active);
        listed.append(area.workbench);
    }

    // Where the user has been, not where they are: the current workbench is
    // already named on the block.
    QStringList recent;
    for (const QString& workbench : recentList()) {
        if (workbench != active && enabled.contains(workbench) && !listed.contains(workbench)) {
            recent.append(workbench);
        }
        if (recent.size() == shownRecent) {
            break;
        }
    }
    if (!recent.isEmpty()) {
        addCaption(tr("Recent"));
        for (const QString& workbench : recent) {
            addWorkbench(workbench, active);
        }
        listed.append(recent);
    }

    QStringList others;
    for (const QString& workbench : enabled) {
        if (!listed.contains(workbench)) {
            others.append(workbench);
        }
    }
    std::sort(others.begin(), others.end(), [this](const QString& a, const QString& b) {
        return titleFor(a).compare(titleFor(b), Qt::CaseInsensitive) < 0;
    });
    if (!others.isEmpty()) {
        addCaption(tr("More workbenches"));
        for (const QString& workbench : others) {
            addWorkbench(workbench, active);
        }
    }

    moveCurrent(1);
}

void WorkbenchSwitcher::addCaption(const QString& text)
{
    auto* item = new QListWidgetItem(text, list);
    item->setFlags(Qt::NoItemFlags);
    QFont font = item->font();
    font.setPointSizeF(std::max(1.0, font.pointSizeF() - 1.0));
    item->setFont(font);
}

void WorkbenchSwitcher::addWorkbench(const QString& workbench, const QString& active)
{
    bool isArea = false;
    for (const Area& area : areas) {
        isArea = isArea || area.workbench == workbench;
    }

    const QString title = titleFor(workbench);
    auto* item = new QListWidgetItem(
        QIcon(Application::Instance->workbenchIcon(workbench)),
        isArea ? asListEntry(title) : title,
        list
    );
    item->setData(workbenchRole, workbench);
    item->setToolTip(Application::Instance->workbenchToolTip(workbench));
    if (workbench == active) {
        QFont font = item->font();
        font.setBold(true);
        item->setFont(font);
    }
}

void WorkbenchSwitcher::moveCurrent(int step)
{
    const int count = list->count();
    if (count == 0) {
        return;
    }

    int row = list->currentRow();
    if (row < 0) {
        row = step > 0 ? -1 : count;
    }
    for (int i = 0; i < count; ++i) {
        row = (row + step + count) % count;
        if (list->item(row)->flags() & Qt::ItemIsEnabled) {
            list->setCurrentRow(row);
            list->scrollToItem(list->item(row));
            return;
        }
    }
}

void WorkbenchSwitcher::activate(QListWidgetItem* item)
{
    if (!item) {
        return;
    }

    const QString workbench = item->data(workbenchRole).toString();
    if (workbench.isEmpty()) {
        return;
    }

    hide();
    Application::Instance->activateWorkbench(workbench.toLatin1().constData());
}

void WorkbenchSwitcher::keyPressEvent(QKeyEvent* event)
{
    if (event->key() == Qt::Key_Escape) {
        hide();
        event->accept();
        return;
    }

    QWidget::keyPressEvent(event);
}

bool WorkbenchSwitcher::eventFilter(QObject* watched, QEvent* event)
{
    if (watched == filter && event->type() == QEvent::KeyPress) {
        const int key = static_cast<QKeyEvent*>(event)->key();
        if (key == Qt::Key_Down || key == Qt::Key_Up) {
            moveCurrent(key == Qt::Key_Down ? 1 : -1);
            return true;
        }
        if (key == Qt::Key_Return || key == Qt::Key_Enter) {
            activate(list->currentItem());
            return true;
        }
    }

    return QWidget::eventFilter(watched, event);
}
