// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <QFrame>
#include <QString>

#include <Mod/Part/PartGlobal.h>

class QLabel;
class QMenu;
class QToolButton;

namespace PartGui
{

/// A Fusion-style pick field: shows what has been picked (or a hint when nothing has),
/// lights up while it is the one the next click in the 3D view goes to, and can carry a
/// menu of quick picks, a clear button and a reverse button. It picks nothing itself;
/// its owner listens to the selection and says whether it is active.
class PartGuiExport PickField: public QFrame
{
    Q_OBJECT
    Q_PROPERTY(bool active READ isActive WRITE setActive NOTIFY activeChanged)
    Q_PROPERTY(QString summary READ shownText)

public:
    enum Part
    {
        QuickPicks = 0x1,
        Clear = 0x2,
        Reverse = 0x4
    };
    Q_DECLARE_FLAGS(Parts, Part)

    explicit PickField(Parts parts = {}, QWidget* parent = nullptr);

    void setSummary(const QString& text);
    void setPlaceholder(const QString& text);
    QString shownText() const;
    bool isEmpty() const;

    void setActive(bool active);
    bool isActive() const;

    void setClearVisible(bool visible);

    void clearQuickPicks();
    void addQuickPick(const QString& text, int id);

Q_SIGNALS:
    void activationRequested();
    void activeChanged(bool active);
    void quickPicked(int id);
    void cleared();
    void reverseClicked();

protected:
    void mouseReleaseEvent(QMouseEvent* event) override;

private:
    void updateLook();

    QLabel* textLabel;
    QToolButton* menuButton = nullptr;
    QToolButton* clearButton = nullptr;
    QToolButton* reverseButton = nullptr;
    QMenu* menu = nullptr;
    QString summaryText;
    QString placeholderText;
    bool active = false;
};

}  // namespace PartGui

Q_DECLARE_OPERATORS_FOR_FLAGS(PartGui::PickField::Parts)
