// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PickField.h"

#include <QHBoxLayout>
#include <QLabel>
#include <QMenu>
#include <QMouseEvent>
#include <QToolButton>

#include <Gui/BitmapFactory.h>

using namespace PartGui;

PickField::PickField(Parts parts, QWidget* parent)
    : QFrame(parent)
    , textLabel(new QLabel(this))
{
    auto* layout = new QHBoxLayout(this);
    layout->setContentsMargins(6, 2, 2, 2);
    layout->setSpacing(2);

    textLabel->setObjectName(QStringLiteral("pickFieldText"));
    textLabel->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Preferred);
    layout->addWidget(textLabel, 1);

    if (parts.testFlag(QuickPicks)) {
        menu = new QMenu(this);
        menuButton = new QToolButton(this);
        menuButton->setObjectName(QStringLiteral("pickFieldMenu"));
        menuButton->setPopupMode(QToolButton::InstantPopup);
        menuButton->setArrowType(Qt::DownArrow);
        menuButton->setToolTip(tr("Choose an axis instead of clicking one"));
        menuButton->setMenu(menu);
        layout->addWidget(menuButton);
    }
    if (parts.testFlag(Clear)) {
        clearButton = new QToolButton(this);
        clearButton->setObjectName(QStringLiteral("pickFieldClear"));
        clearButton->setText(QStringLiteral("✕"));
        clearButton->setToolTip(tr("Remove"));
        connect(clearButton, &QToolButton::clicked, this, &PickField::cleared);
        layout->addWidget(clearButton);
    }
    if (parts.testFlag(Reverse)) {
        reverseButton = new QToolButton(this);
        reverseButton->setObjectName(QStringLiteral("pickFieldReverse"));
        reverseButton->setIcon(Gui::BitmapFactory().iconFromTheme("button_sort"));
        reverseButton->setToolTip(tr("Reverse the direction"));
        connect(reverseButton, &QToolButton::clicked, this, &PickField::reverseClicked);
        layout->addWidget(reverseButton);
    }

    setCursor(Qt::PointingHandCursor);
    updateLook();
}

void PickField::setSummary(const QString& text)
{
    summaryText = text;
    updateLook();
}

void PickField::setPlaceholder(const QString& text)
{
    placeholderText = text;
    updateLook();
}

QString PickField::shownText() const
{
    return summaryText.isEmpty() ? placeholderText : summaryText;
}

bool PickField::isEmpty() const
{
    return summaryText.isEmpty();
}

void PickField::setActive(bool on)
{
    if (active == on) {
        return;
    }
    active = on;
    updateLook();
    Q_EMIT activeChanged(active);
}

bool PickField::isActive() const
{
    return active;
}

void PickField::setClearVisible(bool visible)
{
    if (clearButton) {
        clearButton->setVisible(visible);
    }
}

void PickField::clearQuickPicks()
{
    if (menu) {
        menu->clear();
    }
}

void PickField::addQuickPick(const QString& text, int id)
{
    if (!menu) {
        return;
    }
    QAction* action = menu->addAction(text);
    connect(action, &QAction::triggered, this, [this, id]() { Q_EMIT quickPicked(id); });
}

void PickField::mouseReleaseEvent(QMouseEvent* event)
{
    // The buttons take their own clicks; a click anywhere else is on the field itself
    if (event->button() == Qt::LeftButton && rect().contains(event->position().toPoint())) {
        Q_EMIT activationRequested();
        event->accept();
        return;
    }
    QFrame::mouseReleaseEvent(event);
}

void PickField::updateLook()
{
    textLabel->setText(shownText());
    textLabel->setForegroundRole(isEmpty() ? QPalette::PlaceholderText : QPalette::WindowText);
    // Only this frame, not its buttons: the selector names the class
    setStyleSheet(
        active ? QStringLiteral("PartGui--PickField { border: 2px solid palette(highlight); "
                                "border-radius: 3px; }")
               : QStringLiteral("PartGui--PickField { border: 1px solid palette(mid); "
                                "border-radius: 3px; }")
    );
}

#include "moc_PickField.cpp"  // NOLINT
